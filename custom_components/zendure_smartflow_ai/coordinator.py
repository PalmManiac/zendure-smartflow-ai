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
    DEFAULT_MODE,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str
    price_now: str
    price_export: str

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
    expensive_threshold="input_number.zendure_schwelle_teuer",
    max_charge="input_number.zendure_max_ladeleistung",
    max_discharge="input_number.zendure_max_entladeleistung",
    ac_mode="select.solarflow_2400_ac_ac_mode",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)


def _f(state: str | None, default: float = 0.0) -> float:
    try:
        if state is None:
            return default
        return float(str(state).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator = Daten holen + Entscheidung + direkte Steuerung."""

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
            expensive_threshold=cfg.get("expensive_threshold_entity", DEFAULT_ENTITY_IDS.expensive_threshold),
            max_charge=cfg.get("max_charge_entity", DEFAULT_ENTITY_IDS.max_charge),
            max_discharge=cfg.get("max_discharge_entity", DEFAULT_ENTITY_IDS.max_discharge),
            ac_mode=cfg.get("ac_mode_entity", DEFAULT_ENTITY_IDS.ac_mode),
            input_limit=cfg.get("input_limit_entity", DEFAULT_ENTITY_IDS.input_limit),
            output_limit=cfg.get("output_limit_entity", DEFAULT_ENTITY_IDS.output_limit),
        )

        # ---- GUI Settings (persistiert über entry.options) ----
        opts = entry.options or {}
        self.mode: str = str(opts.get("mode", DEFAULT_MODE))
        self.soc_min: float = float(opts.get("soc_min", DEFAULT_SOC_MIN))
        self.soc_max: float = float(opts.get("soc_max", DEFAULT_SOC_MAX))

        # Freeze / Anti-Flatter
        self._last_recommendation: str | None = None
        self._freeze_until_ts: float = 0.0

        self._last_mode_set: str | None = None
        self._last_in: float | None = None
        self._last_out: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    # ------------------------------------------------------------
    # Persist Settings
    # ------------------------------------------------------------
    async def async_set_setting(self, key: str, value: float) -> None:
        if key == "soc_min":
            self.soc_min = float(value)
        elif key == "soc_max":
            self.soc_max = float(value)

        # in options speichern
        new_opts = dict(self.entry.options or {})
        new_opts[key] = float(value)
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)

        # sofort refresh (damit UI + Logik synchron)
        await self.async_request_refresh()

    async def async_set_mode(self, mode: str) -> None:
        self.mode = str(mode)
        new_opts = dict(self.entry.options or {})
        new_opts["mode"] = self.mode
        self.hass.config_entries.async_update_entry(self.entry, options=new_opts)
        await self.async_request_refresh()

    # ------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------
    def _get_state(self, entity_id: str) -> str | None:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _get_attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        if st is None:
            return None
        return st.attributes.get(attr)

    # ------------------------------------------------------------
    # Zendure control (anti spam)
    # ------------------------------------------------------------
    async def _set_mode(self, mode: str) -> None:
        if mode == self._last_mode_set:
            return
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )
        self._last_mode_set = mode

    async def _set_input_limit(self, watts: float) -> None:
        if self._last_in is not None and abs(self._last_in - watts) < 25:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": float(round(watts, 0))},
            blocking=False,
        )
        self._last_in = watts

    async def _set_output_limit(self, watts: float) -> None:
        if self._last_out is not None and abs(self._last_out - watts) < 25:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": float(round(watts, 0))},
            blocking=False,
        )
        self._last_out = watts

    async def _apply_control(self, mode: str, in_w: float, out_w: float) -> None:
        await self._set_mode(mode)
        await self._set_input_limit(in_w)
        await self._set_output_limit(out_w)

    # ------------------------------------------------------------
    # Prices
    # ------------------------------------------------------------
    def _extract_prices(self) -> list[float]:
        export = self._get_attr(self.entities.price_export, "data")
        if not export:
            return []
        prices: list[float] = []
        for item in export:
            prices.append(_f(item.get("price_per_kwh"), 0.0))
        return prices

    def _idx_now_15min(self) -> int:
        now = dt_util.now()
        minutes = (now.hour * 60) + now.minute
        return int(minutes // 15)

    # ------------------------------------------------------------
    # Update
    # ------------------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now_ts = dt_util.utcnow().timestamp()

            # --- Messwerte ---
            soc = _f(self._get_state(self.entities.soc), 0.0)
            pv = _f(self._get_state(self.entities.pv), 0.0)
            load = _f(self._get_state(self.entities.load), 0.0)
            price_now = _f(self._get_state(self.entities.price_now), 0.0)

            soc_min = float(self.soc_min)
            soc_max = float(self.soc_max)
            soc_notfall = max(soc_min - 4.0, 5.0)

            expensive_threshold = _f(self._get_state(self.entities.expensive_threshold), 0.35)
            max_charge = _f(self._get_state(self.entities.max_charge), 2000.0)
            max_discharge = _f(self._get_state(self.entities.max_discharge), 700.0)

            # --- Preisreihe ---
            prices_all = self._extract_prices()
            idx = self._idx_now_15min()
            future = prices_all[idx:] if idx < len(prices_all) else []

            if future:
                minp = min(future)
                maxp = max(future)
                avg = sum(future) / len(future)
                span = maxp - minp
                dynamic_expensive = avg + span * 0.25
                expensive = max(expensive_threshold, dynamic_expensive)
            else:
                minp = maxp = avg = price_now
                dynamic_expensive = expensive_threshold
                expensive = expensive_threshold

            surplus = max(pv - load, 0.0)

            # ------------------------------------------------
            # Betriebsmodus + Recommendation Freeze
            # ------------------------------------------------
            ai_status = "standby"
            recommendation = "standby"
            control_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # Manuell: NICHT anfassen
            if self.mode == MODE_MANUAL:
                ai_status = "manuell_aktiv"
                recommendation = "standby"
                return {
                    "ai_status": ai_status,
                    "recommendation": recommendation,
                    "debug": "OK",
                    "details": {
                        "mode": self.mode,
                        "soc": soc,
                        "soc_min": soc_min,
                        "soc_max": soc_max,
                    },
                }

            # Freeze aktiv?
            if self._last_recommendation and now_ts < self._freeze_until_ts:
                ai_status = "empfehlung_gehalten"
                recommendation = self._last_recommendation
                # wir setzen NICHT erneut Limits, lassen aber trotzdem apply (anti-spam schützt)
                # (damit beim Neustart konsistent bleibt)
            else:
                # 1) Notfall hat immer Vorrang
                if soc <= soc_notfall and soc < soc_max:
                    ai_status = "notladung"
                    recommendation = "laden"
                    control_mode = "input"
                    in_w = min(max_charge, 300.0)
                    out_w = 0.0

                # 2) Teuer jetzt -> entladen wenn möglich, sonst Akkuschutz
                elif price_now >= expensive:
                    if soc <= soc_min:
                        ai_status = "teuer_akkuschutz"
                        recommendation = "standby"
                        control_mode = "input"
                        in_w = 0.0
                        out_w = 0.0
                    else:
                        ai_status = "teuer_entladen"
                        recommendation = "entladen"
                        control_mode = "output"
                        need = max(load - pv, 0.0)
                        out_w = min(max_discharge, need)
                        in_w = 0.0

                # 3) Sommer: keine Netzladung – nur PV
                elif self.mode == MODE_SUMMER:
                    if surplus > 100 and soc < soc_max:
                        ai_status = "pv_laden"
                        recommendation = "laden"
                        control_mode = "input"
                        in_w = min(max_charge, surplus)
                        out_w = 0.0
                    else:
                        ai_status = "sommer_standby"
                        recommendation = "standby"

                # 4) Winter: (minimal) Netzladung nur im günstigen Bereich
                elif self.mode == MODE_WINTER:
                    # simpel: lade nur wenn wir nahe Minimum sind (günstigste Phase im Future)
                    if future and soc < soc_max and price_now <= (minp + 0.0005):
                        ai_status = "winter_guenstig_laden"
                        recommendation = "laden"
                        control_mode = "input"
                        in_w = max_charge
                        out_w = 0.0
                    elif surplus > 100 and soc < soc_max:
                        ai_status = "pv_laden"
                        recommendation = "laden"
                        control_mode = "input"
                        in_w = min(max_charge, surplus)
                        out_w = 0.0
                    else:
                        ai_status = "winter_standby"
                        recommendation = "standby"

                # 5) Automatik: PV laden, sonst Standby (Teuer/Notfall oben)
                else:
                    if surplus > 100 and soc < soc_max:
                        ai_status = "pv_laden"
                        recommendation = "laden"
                        control_mode = "input"
                        in_w = min(max_charge, surplus)
                        out_w = 0.0
                    else:
                        ai_status = "standby"
                        recommendation = "standby"

                # Freeze setzen bei Änderung
                if recommendation != self._last_recommendation:
                    self._freeze_until_ts = now_ts + 120.0
                    self._last_recommendation = recommendation

            # Steuerung anwenden
            await self._apply_control(control_mode, in_w, out_w)

            details = {
                "mode": self.mode,
                "soc": round(soc, 2),
                "soc_min": round(soc_min, 2),
                "soc_max": round(soc_max, 2),
                "soc_notfall": round(soc_notfall, 2),
                "price_now": round(price_now, 4),
                "min_price_future": round(minp, 4),
                "max_price_future": round(maxp, 4),
                "avg_price_future": round(avg, 4),
                "expensive_effective": round(expensive, 4),
                "expensive_fixed": round(expensive_threshold, 4),
                "expensive_dynamic": round(dynamic_expensive, 4),
                "idx_now": idx,
                "future_len": len(future),
                "pv": round(pv, 1),
                "load": round(load, 1),
                "surplus": round(surplus, 1),
                "max_charge": round(max_charge, 0),
                "max_discharge": round(max_discharge, 0),
                "set_mode": control_mode,
                "set_input_w": round(in_w, 0),
                "set_output_w": round(out_w, 0),
                "freeze_left_s": max(0, int(self._freeze_until_ts - now_ts)),
            }

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": details,
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
