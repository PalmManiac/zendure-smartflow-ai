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
    UPDATE_INTERVAL,
    FREEZE_SECONDS,
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    # Settings
    SETTING_OPERATION_MODE,
    SETTING_MANUAL_ACTION,
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_EXPENSIVE,
    SETTING_PRICE_VERY_EXPENSIVE,
    SETTING_PRICE_CHEAP,
    SETTING_SURPLUS_MIN,
    SETTING_MANUAL_CHARGE_W,
    SETTING_MANUAL_DISCHARGE_W,
    # Defaults
    DEFAULT_OPERATION_MODE,
    DEFAULT_MANUAL_ACTION,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_EXPENSIVE,
    DEFAULT_PRICE_VERY_EXPENSIVE,
    DEFAULT_PRICE_CHEAP,
    DEFAULT_SURPLUS_MIN,
    DEFAULT_MANUAL_CHARGE_W,
    DEFAULT_MANUAL_DISCHARGE_W,
    # Modes / actions
    MODE_AUTOMATIC,
    MODE_SUMMER,
    MODE_WINTER,
    MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityIds:
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
        s = str(val).strip().lower()
        if s in ("unknown", "unavailable", ""):
            return default
        return float(str(val).replace(",", "."))
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
            load=data.get(CONF_LOAD_ENTITY, ""),
            price_export=data.get(CONF_PRICE_EXPORT_ENTITY),
            ac_mode=data.get(CONF_AC_MODE_ENTITY, ""),
            input_limit=data.get(CONF_INPUT_LIMIT_ENTITY, ""),
            output_limit=data.get(CONF_OUTPUT_LIMIT_ENTITY, ""),
        )

        # Anzeige-Freeze (nur recommendation/ai_status)
        self._freeze_until: datetime | None = None
        self._last_recommendation: str | None = None
        self._last_ai_status: str | None = None

        # Anti-Flap / Anti-Spam für Hardware
        self._last_set_mode: str | None = None
        self._last_set_in: float | None = None
        self._last_set_out: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # ------------------------------------------
    # Options (persistente Settings)
    # ------------------------------------------
    def _opt(self, key: str, default: Any) -> Any:
        return (self.entry.options or {}).get(key, default)

    def _is_valid_entity(self, entity_id: str) -> bool:
        if not entity_id:
            return False
        st = self.hass.states.get(entity_id)
        return st is not None and str(st.state).lower() not in ("unknown", "unavailable", "")

    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # ------------------------------------------
    # Price from Tibber "Datenexport" (attributes.data)
    # ------------------------------------------
    def _price_now(self) -> float | None:
        if not self.entities.price_export:
            return None
        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list) or not export:
            return None

        now = dt_util.now()  # local time
        idx = int((now.hour * 60 + now.minute) // 15)
        if idx < 0 or idx >= len(export):
            return None

        item = export[idx]
        if not isinstance(item, dict):
            return None
        return _to_float(item.get("price_per_kwh"), default=None)

    # ------------------------------------------
    # Hardware calls (Zendure)
    # ------------------------------------------
    async def _set_ac_mode(self, mode: str) -> None:
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
            {"entity_id": self.entities.input_limit, "value": float(round(watts, 0))},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        if not self.entities.output_limit:
            return
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": float(round(watts, 0))},
            blocking=False,
        )

    async def _apply_control(self, mode: str, in_w: float, out_w: float) -> None:
        """Only apply if changed enough (prevents flapping)."""
        def changed(last: float | None, new: float, tol: float) -> bool:
            if last is None:
                return True
            return abs(last - new) > tol

        # Mode
        if mode != self._last_set_mode:
            await self._set_ac_mode(mode)
            self._last_set_mode = mode

        # Limits (deadband 25W)
        if changed(self._last_set_in, in_w, 25.0):
            await self._set_input_limit(in_w)
            self._last_set_in = in_w

        if changed(self._last_set_out, out_w, 25.0):
            await self._set_output_limit(out_w)
            self._last_set_out = out_w

    # ------------------------------------------
    # Main update
    # ------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now_utc = dt_util.utcnow()

            # --- Raw States ---
            soc_raw = self._state(self.entities.soc)
            pv_raw = self._state(self.entities.pv)
            load_raw = self._state(self.entities.load)

            soc = _to_float(soc_raw, default=None)
            pv = _to_float(pv_raw, default=None)
            load = _to_float(load_raw, default=None)

            # Settings (Integration Entities -> entry.options)
            op_mode = str(self._opt(SETTING_OPERATION_MODE, DEFAULT_OPERATION_MODE))
            manual_action = str(self._opt(SETTING_MANUAL_ACTION, DEFAULT_MANUAL_ACTION))

            soc_min = float(self._opt(SETTING_SOC_MIN, DEFAULT_SOC_MIN))
            soc_max = float(self._opt(SETTING_SOC_MAX, DEFAULT_SOC_MAX))

            max_charge = float(self._opt(SETTING_MAX_CHARGE, DEFAULT_MAX_CHARGE))
            max_discharge = float(self._opt(SETTING_MAX_DISCHARGE, DEFAULT_MAX_DISCHARGE))

            price_expensive = float(self._opt(SETTING_PRICE_EXPENSIVE, DEFAULT_PRICE_EXPENSIVE))
            price_very_expensive = float(self._opt(SETTING_PRICE_VERY_EXPENSIVE, DEFAULT_PRICE_VERY_EXPENSIVE))
            price_cheap = float(self._opt(SETTING_PRICE_CHEAP, DEFAULT_PRICE_CHEAP))

            surplus_min = float(self._opt(SETTING_SURPLUS_MIN, DEFAULT_SURPLUS_MIN))

            manual_charge_w = float(self._opt(SETTING_MANUAL_CHARGE_W, DEFAULT_MANUAL_CHARGE_W))
            manual_discharge_w = float(self._opt(SETTING_MANUAL_DISCHARGE_W, DEFAULT_MANUAL_DISCHARGE_W))

            # --- Validity check: never stay "Init"
            invalid_reasons: list[str] = []
            if soc is None:
                invalid_reasons.append("soc_invalid")
                soc = 0.0
            if pv is None:
                invalid_reasons.append("pv_invalid")
                pv = 0.0
            if load is None:
                invalid_reasons.append("load_invalid")
                load = 0.0

            price_now = self._price_now()  # optional
            price_valid = price_now is not None

            # Derived
            surplus = max(pv - load, 0.0)
            deficit = max(load - pv, 0.0)

            soc_notfall = max(soc_min - 4.0, 5.0)

            # ------------------------------------------
            # Decision
            # ------------------------------------------
            ai_status = "standby"
            recommendation = "standby"
            debug = "OK"

            set_mode = "input"
            set_in = 0.0
            set_out = 0.0

            # If sensors invalid -> still return data, but don't do risky control
            if invalid_reasons:
                ai_status = "sensor_invalid"
                recommendation = "standby"
                debug = "SENSOR_INVALID"
                # Safety: no forced changes
                set_mode = "input"
                set_in = 0.0
                set_out = 0.0

            else:
                # ==========================
                # MANUAL (übersteuert)
                # ==========================
                if op_mode == MODE_MANUAL:
                    debug = "MANUAL_MODE_ACTIVE"

                    if manual_action == MANUAL_CHARGE and soc < soc_max:
                        ai_status = "manual_charge"
                        recommendation = "laden"
                        set_mode = "input"
                        set_in = max(0.0, min(max_charge, manual_charge_w))
                        set_out = 0.0

                    elif manual_action == MANUAL_DISCHARGE and soc > soc_min:
                        ai_status = "manual_discharge"
                        recommendation = "entladen"
                        set_mode = "output"
                        # Wenn möglich dynamisch ans Defizit koppeln, sonst feste W
                        want = deficit if deficit > 0 else manual_discharge_w
                        set_out = max(0.0, min(max_discharge, want))
                        set_in = 0.0

                    else:
                        ai_status = "manual_standby"
                        recommendation = "standby"
                        set_mode = "input"
                        set_in = 0.0
                        set_out = 0.0

                # ==========================
                # SUMMER (Autarkie)
                # ==========================
                elif op_mode == MODE_SUMMER:
                    debug = "SUMMER_MODE_ACTIVE"

                    # PV Überschuss laden
                    if surplus >= surplus_min and soc < soc_max:
                        ai_status = "pv_überschuss"
                        recommendation = "laden"
                        set_mode = "input"
                        set_in = min(max_charge, surplus)
                        set_out = 0.0

                    # Bei Defizit entladen (Autarkie)
                    elif deficit > 50 and soc > soc_min:
                        ai_status = "autarkie_entladen"
                        recommendation = "entladen"
                        set_mode = "output"
                        set_out = min(max_discharge, deficit)
                        set_in = 0.0

                    else:
                        ai_status = "standby"
                        recommendation = "standby"
                        set_mode = "input"
                        set_in = 0.0
                        set_out = 0.0

                # ==========================
                # WINTER (Preis)
                # ==========================
                elif op_mode == MODE_WINTER:
                    debug = "WINTER_MODE_ACTIVE"

                    # Preis ungültig -> fallback autarkie light
                    if not price_valid:
                        debug = "PRICE_INVALID_FALLBACK"
                        if surplus >= surplus_min and soc < soc_max:
                            ai_status = "pv_überschuss"
                            recommendation = "laden"
                            set_mode = "input"
                            set_in = min(max_charge, surplus)
                        elif deficit > 50 and soc > soc_min:
                            ai_status = "defizit_entladen"
                            recommendation = "entladen"
                            set_mode = "output"
                            set_out = min(max_discharge, deficit)
                        else:
                            ai_status = "standby"
                            recommendation = "standby"

                    else:
                        assert price_now is not None
                        # Sehr teuer -> immer Defizit decken, solange SoC > Min
                        if price_now >= price_very_expensive and soc > soc_min:
                            ai_status = "sehr_teuer_entladen"
                            recommendation = "entladen"
                            set_mode = "output"
                            set_out = min(max_discharge, deficit)
                            set_in = 0.0

                        # Teuer -> entladen wenn möglich
                        elif price_now >= price_expensive and soc > soc_min:
                            ai_status = "teuer_entladen"
                            recommendation = "entladen"
                            set_mode = "output"
                            set_out = min(max_discharge, deficit)
                            set_in = 0.0

                        # Günstig -> laden (auch aus Netz) bis soc_max
                        elif price_now <= price_cheap and soc < soc_max:
                            ai_status = "günstig_laden"
                            recommendation = "laden"
                            set_mode = "input"
                            set_in = max_charge
                            set_out = 0.0

                        # sonst: PV Überschuss laden, optional
                        elif surplus >= surplus_min and soc < soc_max:
                            ai_status = "pv_überschuss"
                            recommendation = "laden"
                            set_mode = "input"
                            set_in = min(max_charge, surplus)
                            set_out = 0.0

                        else:
                            ai_status = "standby"
                            recommendation = "standby"
                            set_mode = "input"
                            set_in = 0.0
                            set_out = 0.0

                # ==========================
                # AUTOMATIC (Mix)
                # ==========================
                else:
                    debug = "AUTO_MODE_ACTIVE"

                    # Notfall: wenn sehr niedrig -> laden (auch ohne Preis)
                    if soc <= soc_notfall and soc < soc_max:
                        ai_status = "notladung"
                        recommendation = "laden"
                        set_mode = "input"
                        set_in = min(max_charge, 300.0)
                        set_out = 0.0

                    # Preislogik, wenn verfügbar
                    elif price_valid and price_now is not None:
                        if price_now >= price_very_expensive and soc > soc_min:
                            ai_status = "sehr_teuer_entladen"
                            recommendation = "entladen"
                            set_mode = "output"
                            set_out = min(max_discharge, deficit)
                            set_in = 0.0

                        elif price_now >= price_expensive and soc > soc_min:
                            ai_status = "teuer_entladen"
                            recommendation = "entladen"
                            set_mode = "output"
                            set_out = min(max_discharge, deficit)
                            set_in = 0.0

                        elif surplus >= surplus_min and soc < soc_max:
                            ai_status = "pv_überschuss"
                            recommendation = "laden"
                            set_mode = "input"
                            set_in = min(max_charge, surplus)
                            set_out = 0.0

                        else:
                            ai_status = "standby"
                            recommendation = "standby"
                            set_mode = "input"
                            set_in = 0.0
                            set_out = 0.0

                    # Ohne Preis: reine Autarkie
                    else:
                        if surplus >= surplus_min and soc < soc_max:
                            ai_status = "pv_überschuss"
                            recommendation = "laden"
                            set_mode = "input"
                            set_in = min(max_charge, surplus)
                            set_out = 0.0
                        elif deficit > 50 and soc > soc_min:
                            ai_status = "defizit_entladen"
                            recommendation = "entladen"
                            set_mode = "output"
                            set_out = min(max_discharge, deficit)
                            set_in = 0.0
                        else:
                            ai_status = "standby"
                            recommendation = "standby"
                            set_mode = "input"
                            set_in = 0.0
                            set_out = 0.0

            # ------------------------------------------
            # Freeze (nur Anzeige)
            # ------------------------------------------
            if self._freeze_until and now_utc < self._freeze_until:
                ai_status_display = self._last_ai_status or ai_status
                recommendation_display = self._last_recommendation or recommendation
            else:
                self._freeze_until = now_utc + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation
                ai_status_display = ai_status
                recommendation_display = recommendation

            # ------------------------------------------
            # Apply hardware (auch wenn price invalid – außer sensor_invalid)
            # ------------------------------------------
            if debug != "SENSOR_INVALID":
                await self._apply_control(set_mode, set_in, set_out)

            return {
                "ai_status": ai_status_display,
                "recommendation": recommendation_display,
                "debug": debug,
                "details": {
                    "operation_mode": op_mode,
                    "manual_action": manual_action,
                    "soc_raw": soc_raw,
                    "pv_raw": pv_raw,
                    "load_raw": load_raw,
                    "soc": round(float(soc), 2),
                    "pv": round(float(pv), 1),
                    "load": round(float(load), 1),
                    "surplus": round(float(surplus), 1),
                    "deficit": round(float(deficit), 1),
                    "price_now": price_now,
                    "price_valid": price_valid,
                    "price_expensive": price_expensive,
                    "price_very_expensive": price_very_expensive,
                    "price_cheap": price_cheap,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "soc_notfall": soc_notfall,
                    "max_charge": max_charge,
                    "max_discharge": max_discharge,
                    "surplus_min": surplus_min,
                    "manual_charge_w": manual_charge_w,
                    "manual_discharge_w": manual_discharge_w,
                    "set_mode": set_mode,
                    "set_input_w": round(set_in, 0),
                    "set_output_w": round(set_out, 0),
                    "freeze_until": self._freeze_until.isoformat() if self._freeze_until else None,
                    "invalid_reasons": invalid_reasons,
                    "entities": {
                        "soc": self.entities.soc,
                        "pv": self.entities.pv,
                        "load": self.entities.load,
                        "price_export": self.entities.price_export,
                        "ac_mode": self.entities.ac_mode,
                        "input_limit": self.entities.input_limit,
                        "output_limit": self.entities.output_limit,
                    },
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
