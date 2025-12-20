from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    # config keys
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
    # settings keys + defaults
    SETTING_MODE,
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD,
    MODE_MANUAL,
    MODE_SUMMER,
    MODE_WINTER,
    MODE_AUTO,
    DEFAULT_MODE,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_EXPORT_CHARGE_MIN_W,
    DEFAULT_IMPORT_DISCHARGE_MIN_W,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = 10  # seconds


@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str

    price_export: str | None

    grid_mode: str
    grid_power: str | None
    grid_import: str | None
    grid_export: str | None

    ac_mode: str
    input_limit: str
    output_limit: str


def _to_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        if value is None:
            return default
        s = str(value).strip()
        if s.lower() in ("unknown", "unavailable", ""):
            return default
        return float(s.replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """V0.2.0: State Machine + integration-owned settings + robust grid topology."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        data = entry.data or {}

        def pick(key: str, default: str | None = None) -> str | None:
            v = data.get(key)
            if v:
                return v
            return default

        self.entities = EntityIds(
            soc=pick(CONF_SOC_ENTITY) or "",
            pv=pick(CONF_PV_ENTITY) or "",
            load=pick(CONF_LOAD_ENTITY) or "",

            price_export=pick(CONF_PRICE_EXPORT_ENTITY),

            grid_mode=pick(CONF_GRID_MODE, GRID_MODE_SINGLE) or GRID_MODE_SINGLE,
            grid_power=pick(CONF_GRID_POWER_ENTITY),
            grid_import=pick(CONF_GRID_IMPORT_ENTITY),
            grid_export=pick(CONF_GRID_EXPORT_ENTITY),

            ac_mode=pick(CONF_AC_MODE_ENTITY) or "",
            input_limit=pick(CONF_INPUT_LIMIT_ENTITY) or "",
            output_limit=pick(CONF_OUTPUT_LIMIT_ENTITY) or "",
        )

        # integration-owned settings (persisted by Restore entities; runtime here)
        self.settings: dict[str, Any] = {
            SETTING_MODE: DEFAULT_MODE,
            SETTING_SOC_MIN: DEFAULT_SOC_MIN,
            SETTING_SOC_MAX: DEFAULT_SOC_MAX,
            SETTING_MAX_CHARGE: DEFAULT_MAX_CHARGE,
            SETTING_MAX_DISCHARGE: DEFAULT_MAX_DISCHARGE,
            SETTING_PRICE_THRESHOLD: DEFAULT_PRICE_THRESHOLD,
        }

        # Anti-Spam for hardware writes
        self._last_hw_mode: str | None = None
        self._last_in_w: float | None = None
        self._last_out_w: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # -------------------------
    # State helpers
    # -------------------------
    def _state(self, entity_id: str | None) -> Any:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str | None, attr: str) -> Any:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # -------------------------
    # Price export -> current slot
    # -------------------------
    def _get_price_now_from_export(self) -> float | None:
        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list) or not export:
            return None

        # robust index: based on first start_time
        try:
            first = export[0]
            start_s = first.get("start_time")
            start_dt = dt_util.parse_datetime(start_s) if start_s else None
            if start_dt is None:
                # fallback: local day index
                now = dt_util.now()
                idx = int((now.hour * 60 + now.minute) // 15)
            else:
                if start_dt.tzinfo is None:
                    start_dt = dt_util.as_local(start_dt)
                else:
                    start_dt = dt_util.as_local(start_dt)

                now_local = dt_util.now()
                delta_min = (now_local - start_dt).total_seconds() / 60.0
                idx = int(delta_min // 15)

            if idx < 0 or idx >= len(export):
                return None

            item = export[idx]
            return _to_float(item.get("price_per_kwh"), default=None)  # type: ignore[arg-type]
        except Exception:
            return None

    # -------------------------
    # Grid import/export read
    # -------------------------
    def _get_grid_import_export(self, pv: float, load: float) -> tuple[float, float, str]:
        """
        Returns: (import_w, export_w, source)
        """
        # Prefer configured grid sensors
        if self.entities.grid_mode == GRID_MODE_SINGLE and self.entities.grid_power:
            grid = _to_float(self._state(self.entities.grid_power), default=None)
            if grid is not None:
                imp = max(grid, 0.0)
                exp = max(-grid, 0.0)
                return imp, exp, "grid_single"

        if self.entities.grid_mode == GRID_MODE_SPLIT and self.entities.grid_import and self.entities.grid_export:
            imp = _to_float(self._state(self.entities.grid_import), default=None)
            exp = _to_float(self._state(self.entities.grid_export), default=None)
            if imp is not None and exp is not None:
                return max(imp, 0.0), max(exp, 0.0), "grid_split"

        # Fallback approximation
        imp2 = max(load - pv, 0.0)
        exp2 = max(pv - load, 0.0)
        return imp2, exp2, "calc_pv_load"

    # -------------------------
    # Hardware (anti-spam)
    # -------------------------
    async def _set_ac_mode(self, mode: str) -> None:
        # mode must be "input" or "output"
        if not self.entities.ac_mode:
            return
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        if not self.entities.input_limit:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": round(float(watts), 0)},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        if not self.entities.output_limit:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": round(float(watts), 0)},
            blocking=False,
        )

    async def _apply_hw(self, mode: str, in_w: float, out_w: float) -> None:
        """Only write when changes are meaningful to avoid flapping."""
        def changed(prev: float | None, new: float, tol: float) -> bool:
            return prev is None or abs(prev - new) > tol

        # Only switch mode if changed
        if mode != self._last_hw_mode:
            await self._set_ac_mode(mode)
            self._last_hw_mode = mode

        # Write limits with tolerance
        if changed(self._last_in_w, in_w, 25.0):
            await self._set_input_limit(in_w)
            self._last_in_w = in_w

        if changed(self._last_out_w, out_w, 25.0):
            await self._set_output_limit(out_w)
            self._last_out_w = out_w

    # -------------------------
    # Main update
    # -------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # Read core sensors
            soc = _to_float(self._state(self.entities.soc), default=None)
            pv = _to_float(self._state(self.entities.pv), default=None)
            load = _to_float(self._state(self.entities.load), default=None)

            if soc is None or pv is None or load is None:
                return {
                    "ai_status": "sensor_invalid",
                    "recommendation": "standby",
                    "debug": "SENSOR_INVALID",
                    "details": {
                        "soc_raw": self._state(self.entities.soc),
                        "pv_raw": self._state(self.entities.pv),
                        "load_raw": self._state(self.entities.load),
                    },
                }

            # Settings (integration-owned)
            mode_sel = str(self.settings.get(SETTING_MODE, DEFAULT_MODE))
            soc_min = float(self.settings.get(SETTING_SOC_MIN, DEFAULT_SOC_MIN))
            soc_max = float(self.settings.get(SETTING_SOC_MAX, DEFAULT_SOC_MAX))
            max_charge = float(self.settings.get(SETTING_MAX_CHARGE, DEFAULT_MAX_CHARGE))
            max_discharge = float(self.settings.get(SETTING_MAX_DISCHARGE, DEFAULT_MAX_DISCHARGE))
            price_threshold = float(self.settings.get(SETTING_PRICE_THRESHOLD, DEFAULT_PRICE_THRESHOLD))

            # Grid I/E
            grid_import, grid_export, grid_src = self._get_grid_import_export(float(pv), float(load))

            # Price now (optional, needed for WINTER/AUTO)
            price_now = self._get_price_now_from_export()

            # Default outputs
            ai_status = "standby"
            recommendation = "standby"
            hw_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # ------------------------------------------------
            # MODE: MANUAL => NO CONTROL (do not override app!)
            # ------------------------------------------------
            if mode_sel == MODE_MANUAL:
                ai_status = "manual_mode_active"
                recommendation = "manual"
                return {
                    "ai_status": ai_status,
                    "recommendation": recommendation,
                    "debug": "MANUAL_MODE_ACTIVE",
                    "details": {
                        "mode": mode_sel,
                        "soc": soc,
                        "pv": pv,
                        "load": load,
                        "grid_import": grid_import,
                        "grid_export": grid_export,
                        "grid_source": grid_src,
                        "price_now": price_now,
                        "note": "No hardware control in MANUAL.",
                    },
                }

            # ------------------------------------------------
            # MODE: SUMMER => Autarkie (PV export -> charge, import -> discharge)
            # ------------------------------------------------
            if mode_sel == MODE_SUMMER:
                # 1) Charge from export if possible
                if grid_export > DEFAULT_EXPORT_CHARGE_MIN_W and soc < soc_max:
                    ai_status = "summer_charge_export"
                    recommendation = "laden"
                    hw_mode = "input"
                    in_w = min(max_charge, grid_export)
                    out_w = 0.0

                # 2) Discharge to cover import (dynamic)
                elif grid_import > DEFAULT_IMPORT_DISCHARGE_MIN_W and soc > soc_min:
                    ai_status = "summer_discharge_import"
                    recommendation = "entladen"
                    hw_mode = "output"
                    out_w = min(max_discharge, grid_import)
                    in_w = 0.0

                else:
                    ai_status = "summer_standby"
                    recommendation = "standby"
                    hw_mode = "input"
                    in_w = 0.0
                    out_w = 0.0

            # ------------------------------------------------
            # MODE: WINTER => Price (threshold discharge), PV export still charges
            # ------------------------------------------------
            elif mode_sel == MODE_WINTER:
                # Always allow charging from export first
                if grid_export > DEFAULT_EXPORT_CHARGE_MIN_W and soc < soc_max:
                    ai_status = "winter_charge_export"
                    recommendation = "laden"
                    hw_mode = "input"
                    in_w = min(max_charge, grid_export)
                    out_w = 0.0

                elif price_now is not None and price_now >= price_threshold and soc > soc_min and grid_import > DEFAULT_IMPORT_DISCHARGE_MIN_W:
                    ai_status = "winter_discharge_expensive"
                    recommendation = "entladen"
                    hw_mode = "output"
                    out_w = min(max_discharge, grid_import)
                    in_w = 0.0

                else:
                    ai_status = "winter_standby"
                    recommendation = "standby"
                    hw_mode = "input"
                    in_w = 0.0
                    out_w = 0.0

            # ------------------------------------------------
            # MODE: AUTO => simple heuristic for V0.2.0 step1
            # ------------------------------------------------
            else:  # MODE_AUTO default
                # If PV/export present -> behave like summer; else winter
                if grid_export > DEFAULT_EXPORT_CHARGE_MIN_W or pv > 200.0:
                    # summer-like
                    if grid_export > DEFAULT_EXPORT_CHARGE_MIN_W and soc < soc_max:
                        ai_status = "auto_charge_export"
                        recommendation = "laden"
                        hw_mode = "input"
                        in_w = min(max_charge, grid_export)
                        out_w = 0.0
                    elif grid_import > DEFAULT_IMPORT_DISCHARGE_MIN_W and soc > soc_min:
                        ai_status = "auto_discharge_import"
                        recommendation = "entladen"
                        hw_mode = "output"
                        out_w = min(max_discharge, grid_import)
                        in_w = 0.0
                    else:
                        ai_status = "auto_standby"
                        recommendation = "standby"
                        hw_mode = "input"
                        in_w = 0.0
                        out_w = 0.0
                else:
                    # winter-like
                    if grid_export > DEFAULT_EXPORT_CHARGE_MIN_W and soc < soc_max:
                        ai_status = "auto_charge_export"
                        recommendation = "laden"
                        hw_mode = "input"
                        in_w = min(max_charge, grid_export)
                        out_w = 0.0
                    elif price_now is not None and price_now >= price_threshold and soc > soc_min and grid_import > DEFAULT_IMPORT_DISCHARGE_MIN_W:
                        ai_status = "auto_discharge_expensive"
                        recommendation = "entladen"
                        hw_mode = "output"
                        out_w = min(max_discharge, grid_import)
                        in_w = 0.0
                    else:
                        ai_status = "auto_standby"
                        recommendation = "standby"
                        hw_mode = "input"
                        in_w = 0.0
                        out_w = 0.0

            # Apply hardware (all non-manual modes)
            await self._apply_hw(hw_mode, in_w, out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "mode": mode_sel,
                    "soc": round(float(soc), 2),
                    "soc_min": round(float(soc_min), 2),
                    "soc_max": round(float(soc_max), 2),
                    "pv": round(float(pv), 1),
                    "load": round(float(load), 1),
                    "grid_import": round(float(grid_import), 1),
                    "grid_export": round(float(grid_export), 1),
                    "grid_source": grid_src,
                    "price_now": price_now,
                    "price_threshold": round(float(price_threshold), 4),
                    "set_mode": hw_mode,
                    "set_input_w": round(float(in_w), 0),
                    "set_output_w": round(float(out_w), 0),
                    "entities": {
                        "soc": self.entities.soc,
                        "pv": self.entities.pv,
                        "load": self.entities.load,
                        "price_export": self.entities.price_export,
                        "grid_mode": self.entities.grid_mode,
                        "grid_power": self.entities.grid_power,
                        "grid_import": self.entities.grid_import,
                        "grid_export": self.entities.grid_export,
                        "ac_mode": self.entities.ac_mode,
                        "input_limit": self.entities.input_limit,
                        "output_limit": self.entities.output_limit,
                    },
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
