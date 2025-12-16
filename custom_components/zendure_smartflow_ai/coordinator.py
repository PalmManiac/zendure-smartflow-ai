from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = 10
FREEZE_SECONDS = 120


# =========================
# Entity IDs
# =========================
@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str

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

    price_export="",

    soc_min="number.zendure_soc_min",
    soc_max="number.zendure_soc_max",
    expensive_threshold="number.zendure_teuer_schwelle",
    max_charge="number.zendure_max_ladeleistung",
    max_discharge="number.zendure_max_entladeleistung",

    ac_mode="select.solarflow_2400_ac_ac_mode",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)


# =========================
# Helper
# =========================
def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return default


# =========================
# Coordinator
# =========================
class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        data = entry.data or {}

        # ✅ Entity-IDs aus ConfigFlow (oder Fallback)
        self.entities = EntityIds(
            soc=data.get("soc_entity", DEFAULT_ENTITY_IDS.soc),
            pv=data.get("pv_entity", DEFAULT_ENTITY_IDS.pv),
            load=data.get("load_entity", DEFAULT_ENTITY_IDS.load),

            price_export=data.get("price_export_entity", ""),

            soc_min=data.get("soc_min_entity", DEFAULT_ENTITY_IDS.soc_min),
            soc_max=data.get("soc_max_entity", DEFAULT_ENTITY_IDS.soc_max),
            expensive_threshold=data.get("expensive_threshold_entity", DEFAULT_ENTITY_IDS.expensive_threshold),
            max_charge=data.get("max_charge_entity", DEFAULT_ENTITY_IDS.max_charge),
            max_discharge=data.get("max_discharge_entity", DEFAULT_ENTITY_IDS.max_discharge),

            ac_mode=data.get("ac_mode_entity", DEFAULT_ENTITY_IDS.ac_mode),
            input_limit=data.get("input_limit_entity", DEFAULT_ENTITY_IDS.input_limit),
            output_limit=data.get("output_limit_entity", DEFAULT_ENTITY_IDS.output_limit),
        )

        # Freeze
        self._freeze_until: datetime | None = None
        self._last_recommendation: str | None = None
        self._last_ai_status: str | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # -------------------------
    # State helpers
    # -------------------------
    def _state(self, entity_id: str) -> str | None:
        s = self.hass.states.get(entity_id)
        return None if s is None else s.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        s = self.hass.states.get(entity_id)
        return None if s is None else s.attributes.get(attr)

    # -------------------------
    # Preis aus Datenexport
    # -------------------------
    def _current_price(self) -> tuple[float | None, int]:
        if not self.entities.price_export:
            return None, 0

        export = self._attr(self.entities.price_export, "data")
        if not export:
            return None, 0

        prices = [_f(e.get("price_per_kwh")) for e in export]

        now = dt_util.now()
        idx = (now.hour * 60 + now.minute) // 15

        if idx >= len(prices):
            return None, idx

        return prices[idx], idx

    # -------------------------
    # Hardware control
    # -------------------------
    async def _set_mode(self, mode: str) -> None:
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": round(watts, 0)},
            blocking=False,
        )

    async def _set_output(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": round(watts, 0)},
            blocking=False,
        )

    # =========================
    # Main update
    # =========================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            soc = _f(self._state(self.entities.soc))
            pv = _f(self._state(self.entities.pv))
            load = _f(self._state(self.entities.load))

            soc_min = _f(self._state(self.entities.soc_min), 12)
            soc_max = _f(self._state(self.entities.soc_max), 95)

            expensive = _f(self._state(self.entities.expensive_threshold), 0.35)
            max_charge = _f(self._state(self.entities.max_charge), 2000)
            max_discharge = _f(self._state(self.entities.max_discharge), 700)

            surplus = max(pv - load, 0)
            soc_notfall = max(soc_min - 4, 5)

            price_now, idx = self._current_price()
            if price_now is None:
                return {
                    "ai_status": "preis_unbekannt",
                    "recommendation": "standby",
                    "debug": "PRICE_INVALID",
                }

            # =========================
            # Entscheidung
            # =========================
            ai_status = "standby"
            recommendation = "standby"
            mode = "input"
            in_w = 0.0
            out_w = 0.0

            if soc <= soc_notfall:
                ai_status = "notladung"
                recommendation = "billig_laden"
                in_w = min(max_charge, 300)

            elif price_now >= expensive and soc > soc_min:
                ai_status = "teuer_jetzt"
                recommendation = "entladen"
                mode = "output"
                out_w = min(max_discharge, max(load - pv, 0))

            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                in_w = min(max_charge, surplus)

            # Freeze
            if self._freeze_until and now < self._freeze_until:
                ai_status = self._last_ai_status or ai_status
                recommendation = self._last_recommendation or recommendation
            else:
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation

            await self._set_mode(mode)
            await self._set_input(in_w)
            await self._set_output(out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "price_now": round(price_now, 4),
                    "price_index": idx,
                    "soc": soc,
                    "surplus": surplus,
                    "set_mode": mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
