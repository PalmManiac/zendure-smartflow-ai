from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    UPDATE_INTERVAL,
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    GRID_MODE_NONE,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
    STATUS_INIT,
    STATUS_OK,
    STATUS_ERROR,
    AI_STATUS_STANDBY,
    AI_STATUS_PRICE_INVALID,
    AI_STATUS_SENSOR_INVALID,
    AI_STATUS_VERY_EXPENSIVE,
    AI_STATUS_EXPENSIVE,
    AI_STATUS_PV_SURPLUS,
    AI_STATUS_MANUAL,
    AI_STATUS_CHARGE,
    AI_STATUS_DISCHARGE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityIds:
    soc: str
    pv: str

    grid_mode: str
    grid_power: str | None
    grid_import: str | None
    grid_export: str | None

    price_export: str | None
    price_now: str | None

    ac_mode: str
    input_limit: str
    output_limit: str


def _to_float(val: Any, default: float | None = None) -> float | None:
    try:
        if val is None:
            return default
        s = str(val).replace(",", ".")
        if s.lower() in ("unknown", "unavailable", ""):
            return default
        return float(s)
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry

        data = entry.data or {}
        self.entities = EntityIds(
            soc=data.get(CONF_SOC_ENTITY, ""),
            pv=data.get(CONF_PV_ENTITY, ""),
            grid_mode=data.get(CONF_GRID_MODE, GRID_MODE_NONE),
            grid_power=data.get(CONF_GRID_POWER_ENTITY) or None,
            grid_import=data.get(CONF_GRID_IMPORT_ENTITY) or None,
            grid_export=data.get(CONF_GRID_EXPORT_ENTITY) or None,
            price_export=data.get(CONF_PRICE_EXPORT_ENTITY) or None,
            price_now=data.get(CONF_PRICE_NOW_ENTITY) or None,
            ac_mode=data.get(CONF_AC_MODE_ENTITY, ""),
            input_limit=data.get(CONF_INPUT_LIMIT_ENTITY, ""),
            output_limit=data.get(CONF_OUTPUT_LIMIT_ENTITY, ""),
        )

        # Runtime settings (werden in number.py gepflegt, hier nur Default-Fallbacks)
        self.runtime_settings: dict[str, float] = {
            "soc_min": DEFAULT_SOC_MIN,
            "soc_max": DEFAULT_SOC_MAX,
            "max_charge": DEFAULT_MAX_CHARGE,
            "max_discharge": DEFAULT_MAX_DISCHARGE,
            "price_threshold": DEFAULT_PRICE_THRESHOLD,
            "very_expensive_threshold": DEFAULT_VERY_EXPENSIVE_THRESHOLD,
        }

        # Runtime mode (wird in select.py gepflegt)
        self.runtime_mode: dict[str, str] = {
            "ai_mode": AI_MODE_AUTOMATIC,
            "manual_action": MANUAL_STANDBY,
        }

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # -------------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # -------------------------
    def _price_now(self) -> float | None:
        # 1) direkter Preis-Sensor (€/kWh)
        if self.entities.price_now:
            v = _to_float(self._state(self.entities.price_now), None)
            if v is not None and v >= 0:
                return v

        # 2) Export-Sensor mit attributes.data (15-Min Slots)
        if not self.entities.price_export:
            return None

        data = self._attr(self.entities.price_export, "data")
        if not isinstance(data, list) or not data:
            return None

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        if idx < 0 or idx >= len(data):
            return None

        try:
            return _to_float(data[idx].get("price_per_kwh"), None)
        except Exception:
            return None

    # -------------------------
    def _grid_power(self) -> float | None:
        gm = self.entities.grid_mode
        if gm == GRID_MODE_NONE:
            return None

        if gm == GRID_MODE_SINGLE:
            if not self.entities.grid_power:
                return None
            return _to_float(self._state(self.entities.grid_power), None)

        # split
        gi = _to_float(self._state(self.entities.grid_import) if self.entities.grid_import else None, 0.0) or 0.0
        ge = _to_float(self._state(self.entities.grid_export) if self.entities.grid_export else None, 0.0) or 0.0
        # net = import - export
        return gi - ge

    # -------------------------
    def _calc_load(self, pv: float, grid: float | None) -> float:
        if grid is None:
            # Ohne Grid können wir Hausverbrauch nicht sicher berechnen -> nutzen PV als Minimum
            return max(pv, 0.0)
        # Hausverbrauch = PV + Netzbezug (positive) oder PV - Einspeisung (negative)
        return max(pv + grid, 0.0)

    # -------------------------
    async def _set_ac_mode(self, mode: str) -> None:
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": round(float(watts), 0)},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": round(float(watts), 0)},
            blocking=False,
        )

    # -------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc_raw = self._state(self.entities.soc)
            pv_raw = self._state(self.entities.pv)

            soc = _to_float(soc_raw, None)
            pv = _to_float(pv_raw, None)

            if soc is None or pv is None:
                return {
                    "status": STATUS_ERROR,
                    "ai_status": AI_STATUS_SENSOR_INVALID,
                    "ai_debug": "SENSOR_INVALID",
                    "recommendation": AI_STATUS_STANDBY,
                    "details": {"soc_raw": soc_raw, "pv_raw": pv_raw},
                }

            grid = self._grid_power()
            load = self._calc_load(pv, grid)

            price_now = self._price_now()

            # Settings
            soc_min = float(self.runtime_settings.get("soc_min", DEFAULT_SOC_MIN))
            soc_max = float(self.runtime_settings.get("soc_max", DEFAULT_SOC_MAX))
            max_charge = float(self.runtime_settings.get("max_charge", DEFAULT_MAX_CHARGE))
            max_discharge = float(self.runtime_settings.get("max_discharge", DEFAULT_MAX_DISCHARGE))
            expensive = float(self.runtime_settings.get("price_threshold", DEFAULT_PRICE_THRESHOLD))
            very_expensive = float(self.runtime_settings.get("very_expensive_threshold", DEFAULT_VERY_EXPENSIVE_THRESHOLD))

            ai_mode = self.runtime_mode.get("ai_mode", AI_MODE_AUTOMATIC)
            manual_action = self.runtime_mode.get("manual_action", MANUAL_STANDBY)

            surplus = max(pv - load, 0.0)
            deficit = max(load - pv, 0.0)

            # Entscheidung
            status = STATUS_OK
            ai_status = AI_STATUS_STANDBY
            recommendation = AI_STATUS_STANDBY

            ac_mode = "input"
            in_w = 0.0
            out_w = 0.0
            debug = "OK"

            # MANUAL hat Vorrang: Hardware wird direkt gesetzt
            if ai_mode == AI_MODE_MANUAL:
                ai_status = AI_STATUS_MANUAL
                recommendation = AI_STATUS_MANUAL

                if manual_action == MANUAL_CHARGE:
                    ai_status = AI_STATUS_CHARGE
                    recommendation = AI_STATUS_CHARGE
                    ac_mode = "input"
                    in_w = min(max_charge, max(surplus, 200.0))
                    out_w = 0.0
                elif manual_action == MANUAL_DISCHARGE:
                    ai_status = AI_STATUS_DISCHARGE
                    recommendation = AI_STATUS_DISCHARGE
                    ac_mode = "output"
                    out_w = min(max_discharge, max(deficit, 200.0))
                    in_w = 0.0
                else:
                    # standby -> kein Eingriff
                    ac_mode = "input"
                    in_w = 0.0
                    out_w = 0.0

            else:
                # Ohne Preisquelle kann Winter/Auto nicht sauber peak-shaven -> Sommerlogik bleibt nutzbar
                if price_now is None and ai_mode in (AI_MODE_AUTOMATIC, AI_MODE_WINTER):
                    ai_status = AI_STATUS_PRICE_INVALID
                    recommendation = AI_STATUS_STANDBY
                    debug = "PRICE_INVALID"
                    # in diesem Fall greifen wir nicht aktiv ein
                    ac_mode = "input"
                    in_w = 0.0
                    out_w = 0.0
                else:
                    # VERY EXPENSIVE -> immer entladen (wenn möglich)
                    if price_now is not None and price_now >= very_expensive and soc > soc_min:
                        ai_status = AI_STATUS_VERY_EXPENSIVE
                        recommendation = AI_STATUS_DISCHARGE
                        ac_mode = "output"
                        out_w = min(max_discharge, deficit)
                        in_w = 0.0

                    # WINTER / AUTOMATIC: teuer -> entladen
                    elif price_now is not None and ai_mode in (AI_MODE_AUTOMATIC, AI_MODE_WINTER):
                        if price_now >= expensive and soc > soc_min:
                            ai_status = AI_STATUS_EXPENSIVE
                            recommendation = AI_STATUS_DISCHARGE
                            ac_mode = "output"
                            out_w = min(max_discharge, deficit)
                            in_w = 0.0

                    # SOMMER / AUTOMATIC: PV Überschuss -> laden
                    if ai_mode in (AI_MODE_AUTOMATIC, AI_MODE_SUMMER):
                        if surplus > 100.0 and soc < soc_max:
                            ai_status = AI_STATUS_PV_SURPLUS
                            recommendation = AI_STATUS_CHARGE
                            ac_mode = "input"
                            in_w = min(max_charge, surplus)
                            out_w = 0.0

            # Hardware anwenden (nur wenn Limits gesetzt werden sollen)
            # Hinweis: Wenn standby -> 0W setzen ist okay (Zendure übernimmt dann)
            await self._set_ac_mode(ac_mode)
            await self._set_input_limit(in_w)
            await self._set_output_limit(out_w)

            return {
                "status": status,
                "ai_status": ai_status,
                "recommendation": recommendation,
                "ai_debug": debug,
                "details": {
                    "soc": soc,
                    "pv": pv,
                    "grid": grid,
                    "load": load,
                    "surplus": surplus,
                    "deficit": deficit,
                    "price_now": price_now,
                    "ai_mode": ai_mode,
                    "manual_action": manual_action,
                    "set_mode": ac_mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
