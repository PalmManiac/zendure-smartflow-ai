from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    UPDATE_INTERVAL,
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    GRID_MODE_NONE,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
    OPT_AI_MODE,
    OPT_MANUAL_ACTION,
    OPT_SOC_MIN,
    OPT_SOC_MAX,
    OPT_MAX_CHARGE,
    OPT_MAX_DISCHARGE,
    OPT_PRICE_THRESHOLD,
    OPT_VERY_EXPENSIVE_THRESHOLD,
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
)

_LOGGER = logging.getLogger(__name__)


def _to_float(val: Any, default: float | None = None) -> float | None:
    try:
        if val is None:
            return default
        s = str(val).strip().lower()
        if s in ("unknown", "unavailable", ""):
            return default
        return float(str(val).replace(",", "."))
    except Exception:
        return default


def _safe_option_match(options: list[str] | None, wanted: str) -> str:
    """Match wanted option to real select options (case-insensitive)."""
    if not options:
        return wanted
    w = wanted.lower()
    for opt in options:
        if str(opt).lower() == w:
            return opt
    return wanted


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry

        data = entry.data or {}

        self.soc_entity = data.get(CONF_SOC_ENTITY, "")
        self.pv_entity = data.get(CONF_PV_ENTITY, "")

        self.price_export_entity = data.get(CONF_PRICE_EXPORT_ENTITY, "")
        self.price_now_entity = data.get(CONF_PRICE_NOW_ENTITY, "")

        self.ac_mode_entity = data.get(CONF_AC_MODE_ENTITY, "")
        self.input_limit_entity = data.get(CONF_INPUT_LIMIT_ENTITY, "")
        self.output_limit_entity = data.get(CONF_OUTPUT_LIMIT_ENTITY, "")

        self.grid_mode = data.get(CONF_GRID_MODE, GRID_MODE_NONE)
        self.grid_power_entity = data.get(CONF_GRID_POWER_ENTITY, "")
        self.grid_import_entity = data.get(CONF_GRID_IMPORT_ENTITY, "")
        self.grid_export_entity = data.get(CONF_GRID_EXPORT_ENTITY, "")

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
    def _read_settings(self) -> dict[str, Any]:
        opt = dict(self.entry.options or {})
        return {
            OPT_AI_MODE: opt.get(OPT_AI_MODE, AI_MODE_AUTOMATIC),
            OPT_MANUAL_ACTION: opt.get(OPT_MANUAL_ACTION, MANUAL_STANDBY),

            OPT_SOC_MIN: float(opt.get(OPT_SOC_MIN, DEFAULT_SOC_MIN)),
            OPT_SOC_MAX: float(opt.get(OPT_SOC_MAX, DEFAULT_SOC_MAX)),
            OPT_MAX_CHARGE: float(opt.get(OPT_MAX_CHARGE, DEFAULT_MAX_CHARGE)),
            OPT_MAX_DISCHARGE: float(opt.get(OPT_MAX_DISCHARGE, DEFAULT_MAX_DISCHARGE)),
            OPT_PRICE_THRESHOLD: float(opt.get(OPT_PRICE_THRESHOLD, DEFAULT_PRICE_THRESHOLD)),
            OPT_VERY_EXPENSIVE_THRESHOLD: float(opt.get(OPT_VERY_EXPENSIVE_THRESHOLD, DEFAULT_VERY_EXPENSIVE_THRESHOLD)),
        }

    # -------------------------
    def _price_now(self) -> float | None:
        # 1) Direkter Preis-Sensor (€/kWh)
        if self.price_now_entity:
            p = _to_float(self._state(self.price_now_entity))
            if p is not None:
                return p

        # 2) Datenexport (attributes.data = list[{start_time, price_per_kwh}])
        if self.price_export_entity:
            data = self._attr(self.price_export_entity, "data")
            if isinstance(data, list) and data:
                now = dt_util.now()
                idx = int((now.hour * 60 + now.minute) // 15)
                if 0 <= idx < len(data):
                    try:
                        return _to_float(data[idx].get("price_per_kwh"))
                    except Exception:
                        return None

        return None

    # -------------------------
    def _grid_power_now(self) -> float | None:
        """Netzleistung: + Bezug / - Einspeisung (W)."""
        if self.grid_mode == GRID_MODE_SINGLE and self.grid_power_entity:
            return _to_float(self._state(self.grid_power_entity))

        if self.grid_mode == GRID_MODE_SPLIT and self.grid_import_entity and self.grid_export_entity:
            imp = _to_float(self._state(self.grid_import_entity), 0.0) or 0.0
            exp = _to_float(self._state(self.grid_export_entity), 0.0) or 0.0
            return imp - exp

        return None

    # -------------------------
    def _calc_load(self, pv: float) -> tuple[float, float]:
        """
        Hausverbrauch approximiert:
        load ≈ pv + grid_net (grid_net + = Bezug, - = Einspeisung)
        """
        gp = self._grid_power_now()
        if gp is None:
            return max(pv, 0.0), 0.0
        load = pv + gp
        return max(load, 0.0), gp

    # -------------------------
    async def _set_ac_mode(self, mode: str) -> None:
        if not self.ac_mode_entity:
            return
        st = self.hass.states.get(self.ac_mode_entity)
        options = list(st.attributes.get("options", [])) if st else None
        real_mode = _safe_option_match(options, mode)

        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.ac_mode_entity, "option": real_mode},
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        if not self.input_limit_entity:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.input_limit_entity, "value": round(float(watts), 0)},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        if not self.output_limit_entity:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.output_limit_entity, "value": round(float(watts), 0)},
            blocking=False,
        )

    # -------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc_raw = self._state(self.soc_entity)
            pv_raw = self._state(self.pv_entity)

            soc = _to_float(soc_raw)
            pv = _to_float(pv_raw)

            if soc is None or pv is None:
                return {
                    "status": "sensor_invalid",
                    "ai_status": "sensor_invalid",
                    "ai_debug": "SENSOR_INVALID",
                    "details": {
                        "soc_raw": soc_raw,
                        "pv_raw": pv_raw,
                        "soc_entity": self.soc_entity,
                        "pv_entity": self.pv_entity,
                    },
                }

            settings = self._read_settings()
            ai_mode = settings[OPT_AI_MODE]
            manual_action = settings[OPT_MANUAL_ACTION]

            soc_min = settings[OPT_SOC_MIN]
            soc_max = settings[OPT_SOC_MAX]
            max_charge = settings[OPT_MAX_CHARGE]
            max_discharge = settings[OPT_MAX_DISCHARGE]
            expensive = settings[OPT_PRICE_THRESHOLD]
            very_expensive = settings[OPT_VERY_EXPENSIVE_THRESHOLD]

            load, grid_power = self._calc_load(pv)
            surplus = max(pv - load, 0.0)
            deficit = max(load - pv, 0.0)

            price_now = self._price_now()

            # -------------------------
            # Decision (default)
            # -------------------------
            status = "online"
            ai_status = "standby"
            ai_debug = "OK"
            recommendation = "standby"

            desired_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # -------------------------
            # Manual mode
            # -------------------------
            if ai_mode == AI_MODE_MANUAL:
                ai_status = "manual"
                ai_debug = "MANUAL_MODE_ACTIVE"

                if manual_action == MANUAL_CHARGE:
                    recommendation = "charge"
                    desired_mode = "input"
                    in_w = max_charge
                    out_w = 0.0

                elif manual_action == MANUAL_DISCHARGE:
                    recommendation = "discharge"
                    desired_mode = "output"
                    out_w = min(max_discharge, max(deficit, 0.0)) if deficit > 0 else max_discharge
                    in_w = 0.0

                else:
                    recommendation = "standby"
                    desired_mode = "input"
                    in_w = 0.0
                    out_w = 0.0

            # -------------------------
            # Summer mode: PV surplus -> charge; deficit -> discharge (if SOC allows)
            # -------------------------
            elif ai_mode == AI_MODE_SUMMER:
                ai_status = "summer"

                if surplus > 80.0 and soc < soc_max:
                    recommendation = "charge"
                    desired_mode = "input"
                    in_w = min(max_charge, surplus)
                    out_w = 0.0

                elif deficit > 80.0 and soc > soc_min:
                    recommendation = "discharge"
                    desired_mode = "output"
                    out_w = min(max_discharge, deficit)
                    in_w = 0.0

                else:
                    recommendation = "standby"
                    desired_mode = "input"
                    in_w = 0.0
                    out_w = 0.0

            # -------------------------
            # Winter/Automatic: price driven if available, otherwise fallback to summer-like behavior
            # -------------------------
            else:
                ai_status = "automatic" if ai_mode == AI_MODE_AUTOMATIC else "winter"

                if price_now is None:
                    ai_debug = "PRICE_MISSING"
                    # fallback behavior (safe)
                    if surplus > 80.0 and soc < soc_max:
                        recommendation = "charge"
                        desired_mode = "input"
                        in_w = min(max_charge, surplus)
                        out_w = 0.0
                    elif deficit > 80.0 and soc > soc_min:
                        recommendation = "discharge"
                        desired_mode = "output"
                        out_w = min(max_discharge, deficit)
                        in_w = 0.0
                    else:
                        recommendation = "standby"
                else:
                    # very expensive: always discharge if possible
                    if price_now >= very_expensive and soc > soc_min:
                        recommendation = "discharge"
                        desired_mode = "output"
                        out_w = min(max_discharge, deficit if deficit > 0 else max_discharge)
                        in_w = 0.0
                        ai_debug = "VERY_EXPENSIVE"

                    elif price_now >= expensive and soc > soc_min:
                        recommendation = "discharge"
                        desired_mode = "output"
                        out_w = min(max_discharge, deficit if deficit > 0 else max_discharge)
                        in_w = 0.0
                        ai_debug = "EXPENSIVE"

                    elif surplus > 80.0 and soc < soc_max:
                        recommendation = "charge"
                        desired_mode = "input"
                        in_w = min(max_charge, surplus)
                        out_w = 0.0
                        ai_debug = "PV_SURPLUS"

                    else:
                        recommendation = "standby"
                        desired_mode = "input"
                        in_w = 0.0
                        out_w = 0.0

            # Apply hardware
            await self._set_ac_mode(desired_mode)
            await self._set_input_limit(in_w)
            await self._set_output_limit(out_w)

            return {
                "status": status,
                "ai_status": ai_status,
                "ai_debug": ai_debug,
                "recommendation": recommendation,
                "details": {
                    "soc": soc,
                    "pv": pv,
                    "load": load,
                    "grid_power": grid_power,
                    "surplus": surplus,
                    "deficit": deficit,
                    "price_now": price_now,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "max_charge": max_charge,
                    "max_discharge": max_discharge,
                    "expensive_threshold": expensive,
                    "very_expensive_threshold": very_expensive,
                    "ai_mode": ai_mode,
                    "manual_action": manual_action,
                    "set_mode": desired_mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
