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
    # flow keys
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    # settings defaults
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    # AI modes
    AI_MODE_AUTO,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ExternalEntities:
    soc: str
    pv: str
    load: str
    price_export: str | None
    ac_mode: str
    input_limit: str
    output_limit: str


def _to_float(val: Any, default: float | None = None) -> float | None:
    try:
        if val is None:
            return default
        s = str(val).strip().replace(",", ".")
        if s.lower() in ("unknown", "unavailable", ""):
            return default
        return float(s)
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Central brain. Platforms read states from coordinator.data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        data = entry.data or {}

        # External entities from flow (required)
        self.external = ExternalEntities(
            soc=str(data.get(CONF_SOC_ENTITY, "")),
            pv=str(data.get(CONF_PV_ENTITY, "")),
            load=str(data.get(CONF_LOAD_ENTITY, "")),
            price_export=(str(data.get(CONF_PRICE_EXPORT_ENTITY)) if data.get(CONF_PRICE_EXPORT_ENTITY) else None),
            ac_mode=str(data.get(CONF_AC_MODE_ENTITY, "")),
            input_limit=str(data.get(CONF_INPUT_LIMIT_ENTITY, "")),
            output_limit=str(data.get(CONF_OUTPUT_LIMIT_ENTITY, "")),
        )

        # Internal settings (stored in-memory; the Number/Select entities own persistence via HA state)
        # Defaults are applied if entities not yet created/available
        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

        # simple anti-flap (don’t hammer control entities every 10s if nothing changes)
        self._last_set: dict[str, Any] = {"mode": None, "in": None, "out": None, "ts": None}

    # ------------------
    # HA state helpers
    # ------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # ------------------
    # Price export (Tibber data export)
    # ------------------
    def _price_now_from_export(self) -> float | None:
        if not self.external.price_export:
            return None
        export = self._attr(self.external.price_export, "data")
        if not isinstance(export, list) or not export:
            return None

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        if idx < 0 or idx >= len(export):
            return None

        item = export[idx]
        if isinstance(item, dict):
            return _to_float(item.get("price_per_kwh"), None)
        return None

    # ------------------
    # internal setting reads (from our own entities)
    # these will exist as HA states once number/select entities are created
    # ------------------
    def _read_setting_number(self, entity_id: str, default: float) -> float:
        return float(_to_float(self._state(entity_id), default) or default)

    def _read_setting_select(self, entity_id: str, default: str) -> str:
        s = self._state(entity_id)
        if s is None:
            return default
        st = str(s).strip().lower()
        return st if st else default

    # ------------------
    # Hardware calls
    # ------------------
    async def _set_ac_mode(self, mode: str) -> None:
        # Zendure options are usually "input"/"output"
        if not self.external.ac_mode:
            return
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.external.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        if not self.external.input_limit:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.external.input_limit, "value": int(round(watts, 0))},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        if not self.external.output_limit:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.external.output_limit, "value": int(round(watts, 0))},
            blocking=False,
        )

    async def _apply_hardware(self, mode: str, in_w: float, out_w: float) -> None:
        """Apply with basic anti-flap: only if changed meaningfully."""
        # don’t set negative
        in_w = max(in_w, 0.0)
        out_w = max(out_w, 0.0)

        # If nothing changed, skip
        if (
            self._last_set["mode"] == mode
            and self._last_set["in"] == int(round(in_w))
            and self._last_set["out"] == int(round(out_w))
        ):
            return

        self._last_set["mode"] = mode
        self._last_set["in"] = int(round(in_w))
        self._last_set["out"] = int(round(out_w))
        self._last_set["ts"] = dt_util.utcnow().isoformat()

        await self._set_ac_mode(mode)
        await self._set_input_limit(in_w)
        await self._set_output_limit(out_w)

    # ------------------
    # Main update
    # ------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # Raw readings
            soc_raw = self._state(self.external.soc)
            pv_raw = self._state(self.external.pv)
            load_raw = self._state(self.external.load)

            soc = float(_to_float(soc_raw, 0.0) or 0.0)
            pv = float(_to_float(pv_raw, 0.0) or 0.0)
            load = float(_to_float(load_raw, 0.0) or 0.0)

            # Price (optional)
            price_now = self._price_now_from_export()

            # Settings from our own entities (they will exist as HA states)
            # If not yet available, fallback to defaults.
            # NOTE: entity_ids are built in number.py/select.py and use unique_id;
            # their entity_id will be stable under the integration device, but HA assigns it.
            # Therefore: we don’t hardcode our own entity_ids here – platforms write values into coordinator via state machine.
            #
            # We solve this by exposing defaults here and platforms pass current values in details.
            #
            # (In 0.7+ we can store these in entry.options. For now: simple.)

            # Decision thresholds (use defaults; sensors/numbers show the editable values)
            soc_min = DEFAULT_SOC_MIN
            soc_max = DEFAULT_SOC_MAX
            max_charge = DEFAULT_MAX_CHARGE
            max_discharge = DEFAULT_MAX_DISCHARGE
            expensive = DEFAULT_PRICE_THRESHOLD

            # NOTE: number/select platforms will push actual values into HA state;
            # We read them by entity_id that we know (created by us with suggested_object_id).
            # To keep it stable and predictable, we define those entity_ids here:
            # number.zendure_smartflow_ai_soc_min etc.
            soc_min = self._read_setting_number("number.zendure_smartflow_ai_soc_min", float(DEFAULT_SOC_MIN))
            soc_max = self._read_setting_number("number.zendure_smartflow_ai_soc_max", float(DEFAULT_SOC_MAX))
            max_charge = self._read_setting_number("number.zendure_smartflow_ai_max_charge", float(DEFAULT_MAX_CHARGE))
            max_discharge = self._read_setting_number(
                "number.zendure_smartflow_ai_max_discharge", float(DEFAULT_MAX_DISCHARGE)
            )
            expensive = self._read_setting_number(
                "number.zendure_smartflow_ai_price_threshold", float(DEFAULT_PRICE_THRESHOLD)
            )

            ai_mode = self._read_setting_select("select.zendure_smartflow_ai_mode", AI_MODE_AUTO)
            manual_action = self._read_setting_select("select.zendure_smartflow_ai_manual_action", MANUAL_STANDBY)

            # Basic computed
            surplus = max(pv - load, 0.0)
            deficit = max(load - pv, 0.0)

            # ----------------------------------------------------
            # Logic output
            # ----------------------------------------------------
            ai_status = "standby"
            recommendation = "standby"
            debug = "OK"

            # Hardware setpoints (only if controlling)
            target_mode = "input"
            target_in = 0.0
            target_out = 0.0

            # ----------------------------------------------------
            # MANUAL: never override user/Zendure control
            # ----------------------------------------------------
            if ai_mode == AI_MODE_MANUAL:
                ai_status = "manual"
                recommendation = "standby"
                debug = "MANUAL_MODE_ACTIVE"
                # Do NOT touch hardware in manual mode
                return {
                    "ai_status": ai_status,
                    "recommendation": recommendation,
                    "debug": debug,
                    "details": {
                        "ai_mode": ai_mode,
                        "manual_action": manual_action,
                        "soc": soc,
                        "pv": pv,
                        "load": load,
                        "surplus": surplus,
                        "deficit": deficit,
                        "price_now": price_now,
                        "soc_min": soc_min,
                        "soc_max": soc_max,
                        "max_charge": max_charge,
                        "max_discharge": max_discharge,
                        "expensive_threshold": expensive,
                    },
                }

            # ----------------------------------------------------
            # SUMMER: maximize autarky:
            # - charge on PV surplus
            # - discharge on deficit in evening/night (no price required)
            # ----------------------------------------------------
            if ai_mode == AI_MODE_SUMMER:
                if surplus > 80.0 and soc < soc_max:
                    ai_status = "pv_surplus"
                    recommendation = "charge"
                    target_mode = "input"
                    target_in = min(max_charge, surplus)
                    target_out = 0.0
                elif deficit > 80.0 and soc > soc_min:
                    ai_status = "cover_load"
                    recommendation = "discharge"
                    target_mode = "output"
                    target_out = min(max_discharge, deficit)
                    target_in = 0.0
                else:
                    ai_status = "standby"
                    recommendation = "standby"
                    target_mode = "input"
                    target_in = 0.0
                    target_out = 0.0

            # ----------------------------------------------------
            # WINTER: price first (if price available), else fallback to autarky discharge
            # ----------------------------------------------------
            elif ai_mode == AI_MODE_WINTER:
                if price_now is None:
                    debug = "PRICE_MISSING"
                    # Without price: still cover deficit if possible
                    if deficit > 80.0 and soc > soc_min:
                        ai_status = "cover_load"
                        recommendation = "discharge"
                        target_mode = "output"
                        target_out = min(max_discharge, deficit)
                    elif surplus > 80.0 and soc < soc_max:
                        ai_status = "pv_surplus"
                        recommendation = "charge"
                        target_mode = "input"
                        target_in = min(max_charge, surplus)
                    else:
                        ai_status = "standby"
                        recommendation = "standby"
                else:
                    # expensive -> discharge
                    if price_now >= expensive and soc > soc_min and deficit > 10.0:
                        ai_status = "expensive_now"
                        recommendation = "discharge"
                        target_mode = "output"
                        target_out = min(max_discharge, deficit)
                        target_in = 0.0
                    # surplus -> charge
                    elif surplus > 80.0 and soc < soc_max:
                        ai_status = "pv_surplus"
                        recommendation = "charge"
                        target_mode = "input"
                        target_in = min(max_charge, surplus)
                        target_out = 0.0
                    else:
                        ai_status = "standby"
                        recommendation = "standby"
                        target_mode = "input"
                        target_in = 0.0
                        target_out = 0.0

            # ----------------------------------------------------
            # AUTO: hybrid
            # ----------------------------------------------------
            else:
                # PV surplus first
                if surplus > 80.0 and soc < soc_max:
                    ai_status = "pv_surplus"
                    recommendation = "charge"
                    target_mode = "input"
                    target_in = min(max_charge, surplus)
                    target_out = 0.0
                # price peak discharge if price present, else autarky discharge
                elif deficit > 80.0 and soc > soc_min:
                    if price_now is None:
                        debug = "PRICE_MISSING"
                        ai_status = "cover_load"
                        recommendation = "discharge"
                        target_mode = "output"
                        target_out = min(max_discharge, deficit)
                        target_in = 0.0
                    else:
                        if price_now >= expensive:
                            ai_status = "expensive_now"
                            recommendation = "discharge"
                            target_mode = "output"
                            target_out = min(max_discharge, deficit)
                            target_in = 0.0
                        else:
                            ai_status = "standby"
                            recommendation = "standby"
                            target_mode = "input"
                            target_in = 0.0
                            target_out = 0.0
                else:
                    ai_status = "standby"
                    recommendation = "standby"
                    target_mode = "input"
                    target_in = 0.0
                    target_out = 0.0

            # Apply hardware (not in manual)
            await self._apply_hardware(target_mode, target_in, target_out)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": debug,
                "details": {
                    "ai_mode": ai_mode,
                    "manual_action": manual_action,
                    "soc_raw": soc_raw,
                    "pv_raw": pv_raw,
                    "load_raw": load_raw,
                    "soc": soc,
                    "pv": pv,
                    "load": load,
                    "surplus": surplus,
                    "deficit": deficit,
                    "price_now": price_now,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "max_charge": max_charge,
                    "max_discharge": max_discharge,
                    "expensive_threshold": expensive,
                    "set_mode": target_mode,
                    "set_input_w": int(round(target_in, 0)),
                    "set_output_w": int(round(target_out, 0)),
                    "external": {
                        "soc": self.external.soc,
                        "pv": self.external.pv,
                        "load": self.external.load,
                        "price_export": self.external.price_export,
                        "ac_mode": self.external.ac_mode,
                        "input_limit": self.external.input_limit,
                        "output_limit": self.external.output_limit,
                    },
                    "last_set": self._last_set,
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
