from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .constants import (
    DOMAIN,
    MODE_AUTOMATIC,
    MODE_MANUAL,
    MODE_SUMMER,
    MODE_WINTER,
)

_LOGGER = logging.getLogger(__name__)


# ------------------------------------------------------------
# Helper
# ------------------------------------------------------------
def _f(state: str | None, default: float = 0.0) -> float:
    try:
        if state is None:
            return default
        return float(str(state).replace(",", "."))
    except Exception:
        return default


# ------------------------------------------------------------
# Entity mapping
# ------------------------------------------------------------
@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str
    price_now: str
    price_export: str

    soc_min: str
    soc_max: str
    expensive_threshold: str
    max_charge: str
    max_discharge: str

    ac_mode: str
    input_limit: str
    output_limit: str


DEFAULT_ENTITY_IDS = EntityIds(
    soc="sensor.solarflow_2400_ac_electric_level",
    pv="sensor.sb2_5_1vl_40_401_pv_power",
    load="sensor.gesamtverbrauch",
    price_now="sensor.paul_schneider_strasse_39_aktueller_strompreis_energie_dashboard",
    price_export="sensor.paul_schneider_strasse_39_diagramm_datenexport",
    soc_min="input_number.zendure_soc_reserve_min",
    soc_max="input_number.zendure_soc_ziel_max",
    expensive_threshold="input_number.zendure_schwelle_teuer",
    max_charge="input_number.zendure_max_ladeleistung",
    max_discharge="input_number.zendure_max_entladeleistung",
    ac_mode="select.solarflow_2400_ac_ac_mode",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)


# ------------------------------------------------------------
# Coordinator
# ------------------------------------------------------------
class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    Zentrale Logik:
    - liest Messwerte & Preise
    - trifft Entscheidung
    - steuert Zendure direkt
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        cfg = entry.data or {}
        self.entities = EntityIds(
            soc=cfg.get("soc_entity", DEFAULT_ENTITY_IDS.soc),
            pv=cfg.get("pv_entity", DEFAULT_ENTITY_IDS.pv),
            load=cfg.get("load_entity", DEFAULT_ENTITY_IDS.load),
            price_now=cfg.get("price_now_entity", DEFAULT_ENTITY_IDS.price_now),
            price_export=cfg.get("price_export_entity", DEFAULT_ENTITY_IDS.price_export),
            soc_min=cfg.get("soc_min_entity", DEFAULT_ENTITY_IDS.soc_min),
            soc_max=cfg.get("soc_max_entity", DEFAULT_ENTITY_IDS.soc_max),
            expensive_threshold=cfg.get("expensive_threshold_entity", DEFAULT_ENTITY_IDS.expensive_threshold),
            max_charge=cfg.get("max_charge_entity", DEFAULT_ENTITY_IDS.max_charge),
            max_discharge=cfg.get("max_discharge_entity", DEFAULT_ENTITY_IDS.max_discharge),
            ac_mode=cfg.get("ac_mode_entity", DEFAULT_ENTITY_IDS.ac_mode),
            input_limit=cfg.get("input_limit_entity", DEFAULT_ENTITY_IDS.input_limit),
            output_limit=cfg.get("output_limit_entity", DEFAULT_ENTITY_IDS.output_limit),
        )

        # Recommendation-Freeze
        self._last_recommendation: str | None = None
        self._freeze_until: float = 0.0

        # Anti-Flatter Schutz
        self._last_mode: str | None = None
        self._last_in: float | None = None
        self._last_out: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    # ------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------
    def _state(self, entity_id: str) -> str | None:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        if st is None:
            return None
        return st.attributes.get(attr)

    # ------------------------------------------------------------
    # Zendure control
    # ------------------------------------------------------------
    async def _set_mode(self, mode: str) -> None:
        if mode == self._last_mode:
            return
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )
        self._last_mode = mode

    async def _set_input(self, watts: float) -> None:
        if self._last_in is not None and abs(self._last_in - watts) < 25:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": round(watts, 0)},
            blocking=False,
        )
        self._last_in = watts

    async def _set_output(self, watts: float) -> None:
        if self._last_out is not None and abs(self._last_out - watts) < 25:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": round(watts, 0)},
            blocking=False,
        )
        self._last_out = watts

    async def _apply(self, mode: str, in_w: float, out_w: float) -> None:
        await self._set_mode(mode)
        await self._set_input(in_w)
        await self._set_output(out_w)

    # ------------------------------------------------------------
    # Price handling
    # ------------------------------------------------------------
    def _prices(self) -> list[float]:
        export = self._attr(self.entities.price_export, "data")
        if not export:
            return []
        return [_f(p.get("price_per_kwh"), 0.0) for p in export]

    def _idx_now(self) -> int:
        now = dt_util.now()
        return (now.hour * 60 + now.minute) // 15

    # ------------------------------------------------------------
    # Core update
    # ------------------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now_ts = dt_util.utcnow().timestamp()

            # --- Read values ---
            soc = _f(self._state(self.entities.soc))
            pv = _f(self._state(self.entities.pv))
            load = _f(self._state(self.entities.load))
            price_now = _f(self._state(self.entities.price_now))

            soc_min = _f(self._state(self.entities.soc_min), 12.0)
            soc_max = _f(self._state(self.entities.soc_max), 95.0)
            soc_notfall = max(soc_min - 4.0, 5.0)

            max_charge = _f(self._state(self.entities.max_charge), 2000.0)
            max_discharge = _f(self._state(self.entities.max_discharge), 700.0)

            expensive_fixed = _f(self._state(self.entities.expensive_threshold), 0.35)

            # --- Prices ---
            prices = self._prices()
            idx = self._idx_now()
            future = prices[idx:] if idx < len(prices) else []

            if future:
                minp = min(future)
                maxp = max(future)
                avgp = sum(future) / len(future)
                dynamic_expensive = avgp + (maxp - minp) * 0.25
                expensive = max(expensive_fixed, dynamic_expensive)
            else:
                minp = maxp = avgp = price_now
                expensive = expensive_fixed
                dynamic_expensive = expensive_fixed

            surplus = max(pv - load, 0.0)

            # ------------------------------------------------
            # Decision
            # ------------------------------------------------
            ai_status = "standby"
            recommendation = "standby"
            mode = "input"
            in_w = 0.0
            out_w = 0.0

            # --- Recommendation-Freeze (120s) ---
            if self._last_recommendation and now_ts < self._freeze_until:
                recommendation = self._last_recommendation
                ai_status = "freeze_active"

            else:
                # 1) Notfall
                if soc <= soc_notfall and soc < soc_max:
                    ai_status = "notladung"
                    recommendation = "laden"
                    mode = "input"
                    in_w = min(max_charge, 300)

                # 2) Teuer jetzt
                elif price_now >= expensive:
                    if soc <= soc_min:
                        ai_status = "teuer_akkuschutz"
                        recommendation = "standby"
                    else:
                        ai_status = "teuer_entladen"
                        recommendation = "entladen"
                        mode = "output"
                        out_w = min(max_discharge, max(load - pv, 0))

                # 3) PV Überschuss
                elif surplus > 100 and soc < soc_max:
                    ai_status = "pv_laden"
                    recommendation = "laden"
                    mode = "input"
                    in_w = min(max_charge, surplus)

                else:
                    ai_status = "standby"
                    recommendation = "standby"

                # Freeze setzen bei Änderung
                if recommendation != self._last_recommendation:
                    self._freeze_until = now_ts + 120
                    self._last_recommendation = recommendation

            # --- Apply control ---
            await self._apply(mode, in_w, out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "soc": round(soc, 2),
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "price_now": round(price_now, 4),
                    "min_price_future": round(minp, 4),
                    "max_price_future": round(maxp, 4),
                    "avg_price_future": round(avgp, 4),
                    "expensive_effective": round(expensive, 4),
                    "expensive_fixed": round(expensive_fixed, 4),
                    "expensive_dynamic": round(dynamic_expensive, 4),
                    "surplus": round(surplus, 1),
                    "mode_set": mode,
                    "input_w": round(in_w, 0),
                    "output_w": round(out_w, 0),
                    "freeze_until": int(self._freeze_until - now_ts),
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
