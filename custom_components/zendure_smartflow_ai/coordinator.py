from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    UPDATE_INTERVAL,
    # config keys
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
    # settings keys (entry.options)
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD,
    SETTING_VERY_EXPENSIVE_THRESHOLD,
    SETTING_EMERGENCY_SOC,
    SETTING_EMERGENCY_CHARGE,
    SETTING_PROFIT_MARGIN_PCT,
    # defaults
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_EMERGENCY_SOC,
    DEFAULT_EMERGENCY_CHARGE,
    DEFAULT_PROFIT_MARGIN_PCT,
    # modes
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
    # statuses
    STATUS_INIT,
    STATUS_OK,
    STATUS_SENSOR_INVALID,
    STATUS_PRICE_INVALID,
    AI_STATUS_STANDBY,
    AI_STATUS_CHARGE_SURPLUS,
    AI_STATUS_COVER_DEFICIT,
    AI_STATUS_EXPENSIVE_DISCHARGE,
    AI_STATUS_VERY_EXPENSIVE_FORCE,
    AI_STATUS_EMERGENCY_CHARGE,
    AI_STATUS_MANUAL,
    RECO_STANDBY,
    RECO_CHARGE,
    RECO_DISCHARGE,
    RECO_EMERGENCY,
    ZENDURE_MODE_INPUT,
    ZENDURE_MODE_OUTPUT,
)

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1


def _to_float(v: Any, default: float | None = None) -> float | None:
    try:
        if v is None:
            return default
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if s == "" or s.lower() in ("unknown", "unavailable", "none"):
            return default
        return float(s)
    except Exception:
        return default


@dataclass
class SelectedEntities:
    soc: str
    pv: str
    price_export: str | None
    price_now: str | None
    ac_mode: str
    input_limit: str
    output_limit: str

    grid_mode: str
    grid_power: str | None
    grid_import: str | None
    grid_export: str | None


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        # runtime settings mirror of entry.options (used by number entities)
        self.runtime_settings: dict[str, float] = dict(entry.options)

        self.entities = SelectedEntities(
            soc=str(entry.data[CONF_SOC_ENTITY]),
            pv=str(entry.data[CONF_PV_ENTITY]),
            price_export=entry.data.get(CONF_PRICE_EXPORT_ENTITY),
            price_now=entry.data.get(CONF_PRICE_NOW_ENTITY),
            ac_mode=str(entry.data[CONF_AC_MODE_ENTITY]),
            input_limit=str(entry.data[CONF_INPUT_LIMIT_ENTITY]),
            output_limit=str(entry.data[CONF_OUTPUT_LIMIT_ENTITY]),
            grid_mode=str(entry.data.get(CONF_GRID_MODE, GRID_MODE_NONE)),
            grid_power=entry.data.get(CONF_GRID_POWER_ENTITY),
            grid_import=entry.data.get(CONF_GRID_IMPORT_ENTITY),
            grid_export=entry.data.get(CONF_GRID_EXPORT_ENTITY),
        )

        self.runtime_mode: dict[str, Any] = {
            "ai_mode": AI_MODE_AUTOMATIC,
            "manual_action": MANUAL_STANDBY,
        }

        self._store = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._persist: dict[str, Any] = {
            "runtime_mode": dict(self.runtime_mode),

            # --- anti-oscillation / hysteresis ---
            "pv_surplus_cnt": 0,
            "pv_clear_cnt": 0,

            # emergency latch
            "emergency_active": False,

            # --- V1.2/1.4 planning ---
            "planning_checked": False,
            "planning_status": "not_checked",
            "planning_blocked_by": None,
            "planning_active": False,
            "planning_target_soc": None,
            "planning_next_peak": None,
            "planning_reason": None,

            # analytics
            "trade_avg_charge_price": None,
            "trade_charged_kwh": 0.0,
            "prev_soc": None,

            # last applied setpoints (for change detection / avoiding service spam)
            "last_set_mode": None,
            "last_set_input_w": None,
            "last_set_output_w": None,

            "avg_charge_price": None,
            "charged_kwh": 0.0,
            "discharged_kwh": 0.0,
            "discharge_target_w": 0.0,
            "profit_eur": 0.0,
            "last_ts": None,
            "power_state": "idle",  # idle | discharging | charging

            # --- V1.3.x transparency ---
            "next_action_time": None,

            # --- smoothing / EMA ---
            "ema_deficit": None,
            "ema_surplus": None,
            "ema_house_load": None,
            "ema_last_ts": None,

            # output smoothing timestamps (manual/discharge)
            "last_output_ts": None,

            # --- V1.4.0 price planning (future transparency) ---
            "next_planned_action": None,          # charge | discharge | wait | emergency | none
            "next_planned_action_time": None,     # ISO timestamp
        }

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _load(self) -> None:
        data = await self._store.async_load()
        if isinstance(data, dict):
            self._persist.update(data)
            if "runtime_mode" in data and isinstance(data["runtime_mode"], dict):
                self.runtime_mode.update(data["runtime_mode"])

    async def _save(self) -> None:
        self._persist["runtime_mode"] = dict(self.runtime_mode)
        await self._store.async_save(self._persist)

    def _state(self, entity_id: str | None) -> Any:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return st.state if st else None

    def _attr(self, entity_id: str | None, attr: str) -> Any:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        if not st:
            return None
        return st.attributes.get(attr)

    def set_ai_mode(self, mode: str) -> None:
        self.runtime_mode["ai_mode"] = mode

    def set_manual_action(self, action: str) -> None:
        self.runtime_mode["manual_action"] = action

    async def _set_ac_mode(self, mode: str) -> None:
        """Set AC mode only when it changes (avoid service spam / HA lag)."""
        last = self._persist.get("last_set_mode")
        # Im manuellen Modus IMMER setzen, auch wenn der Modus gleich ist
        if self.runtime_mode.get("ai_mode") != AI_MODE_MANUAL:
            if last == mode:
                return
        self._persist["last_set_mode"] = mode
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        """Set input limit only when it changes (avoid service spam / HA lag)."""
        val = int(round(float(watts), 0))
        last = self._persist.get("last_set_input_w")
        if last == val:
            return
        self._persist["last_set_input_w"] = val
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": val},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        """Set output limit only when it changes (avoid service spam / HA lag)."""
        val = int(round(float(watts), 0))
        last = self._persist.get("last_set_output_w")
        if last == val:
            return
        self._persist["last_set_output_w"] = val
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": val},
            blocking=False,
        )

    # --------------------------------------------------
    # settings (stored in config entry options)
    # --------------------------------------------------
    def _get_setting(self, key: str, default: float) -> float:
        try:
            val = self.entry.options.get(key, default)
            return float(val)
        except Exception:
            return float(default)

    def _get_grid(self) -> tuple[float | None, float | None]:
        """
        Returns (deficit_w, surplus_w).
        deficit_w > 0 means importing from grid
        surplus_w > 0 means exporting to grid
        """
        mode = self.entities.grid_mode

        if mode == GRID_MODE_NONE:
            return None, None

        if mode == GRID_MODE_SINGLE and self.entities.grid_power:
            gp = _to_float(self._state(self.entities.grid_power), None)
            if gp is None:
                return None, None
            gp = float(gp)
            if gp >= 0:
                return gp, 0.0
            return 0.0, abs(gp)

        if mode == GRID_MODE_SPLIT and self.entities.grid_import and self.entities.grid_export:
            gi = _to_float(self._state(self.entities.grid_import), None)
            ge = _to_float(self._state(self.entities.grid_export), None)
            if gi is None or ge is None:
                return None, None
            return float(gi), float(ge)

        return None, None

    def _get_price_now(self) -> float | None:
        if self.entities.price_now:
            p = _to_float(self._state(self.entities.price_now), None)
            if p is not None:
                return float(p)
        return None

    def _evaluate_price_planning(
        self,
        soc: float,
        soc_max: float,
        price_now: float | None,
        expensive: float,
        very_expensive: float,
        profit_margin_pct: float,
        max_charge: float,
        surplus_w: float | None,
        ai_mode: str,
    ) -> dict[str, Any]:
        """Price planning: find future peak, then locate cheap window before it."""
        result: dict[str, Any] = {
            "action": "none",
            "watts": 0.0,
            "status": "not_checked",
            "blocked_by": None,
            "next_peak": None,
            "reason": None,
            "latest_start": None,
            "target_soc": None,
        }

        if ai_mode != AI_MODE_AUTOMATIC:
            result.update(status="planning_inactive_mode", blocked_by="mode")
            return result

        if float(soc) >= float(soc_max) - 0.1:
            result.update(status="planning_blocked_soc_full", blocked_by="soc")
            return result

        if price_now is None:
            result.update(status="planning_no_price_now", blocked_by="price_now")
            return result

        if not self.entities.price_export:
            result.update(status="planning_no_price_data", blocked_by="price_data")
            return result

        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list):
            result.update(status="planning_no_price_data", blocked_by="price_data")
            return result

        now = dt_util.utcnow()

        # Build future series (timestamp, price)
        future: list[tuple[Any, float]] = []
        for item in export:
            if not isinstance(item, dict):
                continue

            ts = item.get("starts_at") or item.get("start") or item.get("time")
            p = _to_float(item.get("price_per_kwh"), None)
            if not ts or p is None:
                continue

            t = dt_util.parse_datetime(str(ts))
            if not t:
                continue

            # Keep only future points
            if t > now:
                future.append((t, float(p)))

        if len(future) < 8:
            result.update(status="planning_no_price_data", blocked_by="price_data")
            return result

        # Peak detection (max price in future)
        peak_time, peak_price = max(future, key=lambda x: x[1])

        # No relevant peak -> nothing to do
        if float(peak_price) < float(expensive) and float(peak_price) < float(very_expensive):
            result.update(status="planning_no_peak_detected", blocked_by=None)
            return result

        # Target price (simple: peak * (1 - margin))
        margin = max(float(profit_margin_pct or 0.0), 0.0) / 100.0
        target_price = float(peak_price) * (1.0 - margin)

        pre_peak = [(t, p) for (t, p) in future if t < peak_time]
        if len(pre_peak) < 4:
            result.update(status="planning_peak_detected_insufficient_window", blocked_by="price_data")
            return result

        cheap_slots = [(t, p) for (t, p) in pre_peak if float(p) <= float(target_price)]
        if not cheap_slots:
            result.update(
                status="planning_waiting_for_cheap_window",
                blocked_by="price_data",
                next_peak=peak_time.isoformat(),
                reason="waiting_for_cheap_price",
            )
            return result

        latest_cheap_time, latest_cheap_price = max(cheap_slots, key=lambda x: x[0])
        target_soc = min(float(soc_max), float(soc) + 30.0)

        # In cheap slot now -> charge now
        if float(price_now) <= float(target_price):
            watts = max(float(max_charge), 0.0)
            result.update(
                action="charge",
                watts=watts,
                status="planning_charge_now",
                next_peak=peak_time.isoformat(),
                reason="charge_before_price_peak",
                latest_start=latest_cheap_time.isoformat(),
                target_soc=target_soc,
            )
            return result

        # Not cheap yet -> wait, but expose when latest cheap start is
        result.update(
            action="none",
            status="planning_waiting_for_cheap_window",
            next_peak=peak_time.isoformat(),
            reason="waiting_for_cheap_price",
            latest_start=latest_cheap_time.isoformat(),
            target_soc=target_soc,
        )
        return result

    # --------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # load persisted state once
            if self._persist.get("last_ts") is None:
                await self._load()
                self._persist["last_ts"] = dt_util.utcnow().isoformat()

            now = dt_util.utcnow()

            # SAFE DEFAULTS
            house_load = 0.0
            surplus = 0.0
            deficit_raw = 0.0
            pv_w = 0.0
            price_now = None

            soc = _to_float(self._state(self.entities.soc), None)
            pv = _to_float(self._state(self.entities.pv), None)

            # EMA helper
            EMA_TAU_S = 45.0
            now_ts = now.timestamp()

            last_ts = self._persist.get("ema_last_ts")
            if last_ts is None:
                dt = None
            else:
                dt = max(now_ts - float(last_ts), 0.0)

            alpha = 1.0 if dt is None or dt <= 0 else min(dt / (EMA_TAU_S + dt), 1.0)

            def _ema(key: str, value: float) -> float:
                prev = self._persist.get(key)
                if prev is None:
                    self._persist[key] = float(value)
                    return float(value)
                v = (1.0 - alpha) * float(prev) + alpha * float(value)
                self._persist[key] = float(v)
                return float(v)

            # Update EMA timestamp NOW (fix: otherwise EMA never progresses correctly)
            self._persist["ema_last_ts"] = float(now_ts)

            if soc is None or pv is None:
                return {
                    "status": STATUS_SENSOR_INVALID,
                    "ai_status": AI_STATUS_STANDBY,
                    "recommendation": RECO_STANDBY,
                    "debug": "SENSOR_INVALID",
                    "details": {
                        "soc_raw": self._state(self.entities.soc),
                        "pv_raw": self._state(self.entities.pv),
                    },
                    "decision_reason": "sensor_invalid",
                }

            soc = float(soc)
            pv = float(pv)

            soc_min = self._get_setting(SETTING_SOC_MIN, DEFAULT_SOC_MIN)
            soc_max = self._get_setting(SETTING_SOC_MAX, DEFAULT_SOC_MAX)
            max_charge = self._get_setting(SETTING_MAX_CHARGE, DEFAULT_MAX_CHARGE)
            max_discharge = self._get_setting(SETTING_MAX_DISCHARGE, DEFAULT_MAX_DISCHARGE)

            expensive = self._get_setting(SETTING_PRICE_THRESHOLD, DEFAULT_PRICE_THRESHOLD)
            very_expensive = self._get_setting(SETTING_VERY_EXPENSIVE_THRESHOLD, DEFAULT_VERY_EXPENSIVE_THRESHOLD)
            emergency_soc = self._get_setting(SETTING_EMERGENCY_SOC, DEFAULT_EMERGENCY_SOC)
            emergency_w = self._get_setting(SETTING_EMERGENCY_CHARGE, DEFAULT_EMERGENCY_CHARGE)
            profit_margin_pct = self._get_setting(SETTING_PROFIT_MARGIN_PCT, DEFAULT_PROFIT_MARGIN_PCT)

            ai_mode = self.runtime_mode.get("ai_mode", AI_MODE_AUTOMATIC)
            manual_action = self.runtime_mode.get("manual_action", MANUAL_STANDBY)

            deficit_raw, surplus_raw = self._get_grid()
            price_now = self._get_price_now()

            deficit_raw = float(deficit_raw) if deficit_raw is not None else 0.0
            no_deficit = deficit_raw <= 30.0
            surplus_raw = float(surplus_raw) if surplus_raw is not None else 0.0
            surplus = _ema("ema_surplus", surplus_raw)

            # HOUSE LOAD
            pv_w = float(pv)
            grid_import = deficit_raw if deficit_raw > 0.0 else 0.0
            grid_export = surplus_raw if surplus_raw > 0.0 else 0.0

            house_load_raw = pv_w + grid_import - grid_export
            house_load_raw = max(house_load_raw, 0.0)
            house_load = _ema("ema_house_load", house_load_raw) or house_load_raw
            no_house_load = house_load < 120.0

            # Winter detection
            is_winter_mode = (
                ai_mode in (AI_MODE_WINTER, AI_MODE_AUTOMATIC)
                and surplus < 50.0
                and price_now is not None
                and price_now < expensive
            )

            # PV surplus hysteresis
            PV_STOP_W = 80.0
            PV_CLEAR_W = 30.0
            PV_STOP_N = 3
            PV_CLEAR_N = 6

            if surplus > PV_STOP_W:
                self._persist["pv_surplus_cnt"] = int(self._persist.get("pv_surplus_cnt") or 0) + 1
                self._persist["pv_clear_cnt"] = 0
            else:
                self._persist["pv_surplus_cnt"] = 0
                if surplus < PV_CLEAR_W:
                    self._persist["pv_clear_cnt"] = int(self._persist.get("pv_clear_cnt") or 0) + 1
                else:
                    self._persist["pv_clear_cnt"] = 0

            pv_stop_discharge = int(self._persist.get("pv_surplus_cnt") or 0) >= PV_STOP_N

            # Emergency latch
            if soc <= emergency_soc:
                self._persist["emergency_active"] = True
            if self._persist.get("emergency_active") and soc >= soc_min:
                self._persist["emergency_active"] = False

            # Decide setpoints
            status = STATUS_OK
            ac_mode = ZENDURE_MODE_INPUT
            in_w = 0.0
            out_w = 0.0
            recommendation = RECO_STANDBY
            decision_reason = "standby"
            prev_power_state = str(self._persist.get("power_state") or "idle")
            power_state = prev_power_state

            # reset planning flags each cycle
            self._persist["planning_checked"] = False
            self._persist["planning_status"] = "not_checked"
            self._persist["planning_blocked_by"] = None
            self._persist["planning_active"] = False
            self._persist["planning_reason"] = None
            self._persist["planning_target_soc"] = None
            self._persist["planning_next_peak"] = None

            # Evaluate planning (Beta2: now also affects control when "charge_now")
            planning = self._evaluate_price_planning(
                soc=soc,
                soc_max=soc_max,
                price_now=price_now,
                expensive=expensive,
                very_expensive=very_expensive,
                profit_margin_pct=profit_margin_pct,
                max_charge=max_charge,
                surplus_w=surplus,
                ai_mode=ai_mode,
            )

            self._persist["planning_checked"] = True
            self._persist["planning_status"] = planning.get("status")
            self._persist["planning_blocked_by"] = planning.get("blocked_by")
            self._persist["planning_reason"] = planning.get("reason")
            self._persist["planning_target_soc"] = planning.get("target_soc")
            self._persist["planning_next_peak"] = planning.get("next_peak")

            # --------------------------------------------------
            # PRICE PLANNING OVERRIDE (Beta2): charge in cheap window
            # IMPORTANT: must not be overwritten by the state machine afterwards
            # --------------------------------------------------
            planning_override = False
            if (
                ai_mode == AI_MODE_AUTOMATIC
                and planning.get("action") == "charge"
                and planning.get("status") == "planning_charge_now"
                and soc < float(planning.get("target_soc") or soc_max)
                and not self._persist.get("emergency_active")
            ):
                planning_override = True
                self._persist["planning_active"] = True

                ac_mode = ZENDURE_MODE_INPUT
                in_w = float(max_charge)
                out_w = 0.0
                recommendation = RECO_CHARGE
                decision_reason = "planning_charge_before_peak"
                self._persist["power_state"] = "charging"
                power_state = "charging"

            # 1) emergency always wins (can override planning)
            if self._persist.get("emergency_active"):
                planning_override = False  # emergency overrides everything
                self._persist["planning_active"] = False

                ac_mode = ZENDURE_MODE_INPUT
                recommendation = RECO_EMERGENCY
                in_w = min(max_charge, max(float(emergency_w), 0.0))
                out_w = 0.0
                decision_reason = "emergency_latched_charge"
                self._persist["power_state"] = "charging"
                power_state = "charging"

            # 2) manual mode
            elif ai_mode == AI_MODE_MANUAL:
                planning_override = False
                self._persist["planning_active"] = False

                recommendation = RECO_STANDBY
                decision_reason = "manual_mode"
                self._persist["power_state"] = "idle"
                power_state = "idle"

                if manual_action == MANUAL_STANDBY:
                    ac_mode = ZENDURE_MODE_INPUT
                    in_w = 0.0
                    out_w = 0.0
                    recommendation = RECO_STANDBY
                    decision_reason = "manual_standby"

                elif manual_action == MANUAL_CHARGE:
                    ac_mode = ZENDURE_MODE_INPUT
                    in_w = float(max_charge)
                    out_w = 0.0
                    self._persist["power_state"] = "charging"
                    power_state = "charging"
                    recommendation = RECO_CHARGE
                    decision_reason = "manual_charge"

                elif manual_action == MANUAL_DISCHARGE:
                    ac_mode = ZENDURE_MODE_OUTPUT
                    in_w = 0.0

                    prev_target = float(self._persist.get("discharge_target_w") or 0.0)
                    raw_target = float(deficit_raw)

                    MAX_STEP = 250.0
                    if raw_target > prev_target:
                        target = min(prev_target + MAX_STEP, raw_target)
                    else:
                        target = max(prev_target - MAX_STEP, raw_target)

                    self._persist["discharge_target_w"] = float(target)
                    out_w = min(float(max_discharge), max(float(target), 0.0))
                    recommendation = RECO_DISCHARGE
                    decision_reason = "manual_discharge"

            # 3) automatic state machine (only if planning is NOT overriding)
            elif ai_mode != AI_MODE_MANUAL and not planning_override:

                if power_state == "discharging" and pv_stop_discharge:
                    power_state = "charging"
                    self._persist["power_state"] = "charging"

                if power_state == "charging" and (soc >= soc_max or surplus <= 0.0):
                    power_state = "idle"
                    self._persist["power_state"] = "idle"

                if power_state == "discharging":
                    no_deficit = deficit_raw <= 30.0
                    no_house_load = house_load <= 50.0

                if no_deficit or no_house_load:
                    power_state = "idle"
                    self._persist["power_state"] = "idle"
                    self._persist["discharge_target_w"] = 0.0

                if power_state == "discharging" and soc <= soc_min:
                    power_state = "idle"
                    self._persist["power_state"] = "idle"

                if power_state == "idle":
                    if (
                        not is_winter_mode
                        and house_load > 150.0
                        and deficit_raw > 80.0
                        and soc > soc_min
                    ):
                        power_state = "discharging"
                        self._persist["power_state"] = "discharging"
                        decision_reason = "state_enter_discharge"

                    elif surplus > 80.0 and soc < soc_max:
                        power_state = "charging"
                        self._persist["power_state"] = "charging"
                        decision_reason = "state_enter_charge"

                    else:
                        decision_reason = "state_idle"

                    if house_load < 120.0:
                        power_state = "idle"
                        self._persist["power_state"] = "idle"

                if power_state == "discharging":
                    ac_mode = ZENDURE_MODE_OUTPUT
                    recommendation = RECO_DISCHARGE

                    prev_target = float(self._persist.get("discharge_target_w") or 0.0)
                    house_target = house_load + prev_target
                    raw_target = min(house_target, max_discharge)

                    MAX_STEP_UP = 120.0
                    MAX_STEP_DOWN = 40.0
                    if raw_target > prev_target:
                        target = min(prev_target + MAX_STEP_UP, raw_target)
                    else:
                        target = max(prev_target - MAX_STEP_DOWN, raw_target)

                    self._persist["discharge_target_w"] = float(target)
                    out_w = min(float(max_discharge), max(float(target), 0.0))
                    in_w = 0.0
                    decision_reason = decision_reason if decision_reason.startswith("state_enter") else "state_discharging"

                elif power_state == "charging":
                    ac_mode = ZENDURE_MODE_INPUT
                    recommendation = RECO_CHARGE
                    in_w = min(float(max_charge), max(float(surplus), 0.0))
                    out_w = 0.0
                    decision_reason = decision_reason if decision_reason.startswith("state_enter") else "state_charging"

                else:
                    ac_mode = ZENDURE_MODE_INPUT
                    recommendation = RECO_STANDBY
                    in_w = 0.0
                    out_w = 0.0
                    self._persist["discharge_target_w"] = 0.0

                RESERVE_SOC = float(soc_min) + 5.0

                if price_now is not None and soc > RESERVE_SOC and power_state != "charging":
                    if price_now >= very_expensive:
                        ac_mode = ZENDURE_MODE_OUTPUT
                        recommendation = RECO_DISCHARGE
                        out_w = min(float(max_discharge), max(float(deficit_raw), 0.0))
                        in_w = 0.0
                        decision_reason = "very_expensive_force_discharge"
                        self._persist["power_state"] = "discharging"
                        power_state = "discharging"
                    elif price_now >= expensive and power_state == "idle" and deficit_raw > 0.0:
                        ac_mode = ZENDURE_MODE_OUTPUT
                        recommendation = RECO_DISCHARGE
                        prev_target = float(self._persist.get("discharge_target_w") or 0.0)
                        raw_target = float(deficit_raw)
                        MAX_STEP_UP = 250.0
                        if raw_target > prev_target:
                            target = min(prev_target + MAX_STEP_UP, raw_target)
                        else:
                            target = prev_target
                        self._persist["discharge_target_w"] = float(target)
                        out_w = min(float(max_discharge), max(float(target), 0.0))
                        in_w = 0.0
                        decision_reason = "expensive_discharge"
                        self._persist["power_state"] = "discharging"
                        power_state = "discharging"

            # enforce SoC-min on discharge
            if ac_mode == ZENDURE_MODE_OUTPUT and soc <= soc_min:
                ac_mode = ZENDURE_MODE_INPUT
                out_w = 0.0
                if recommendation == RECO_DISCHARGE:
                    recommendation = RECO_STANDBY
                decision_reason = "soc_min_enforced"

            # Apply hardware setpoints
            if ac_mode == ZENDURE_MODE_OUTPUT:
                in_w = 0.0
            if ac_mode == ZENDURE_MODE_INPUT:
                out_w = 0.0

            # Zendure requires output_limit=0 before AC input
            if ac_mode == ZENDURE_MODE_INPUT:
                if self._persist.get("last_set_output_w", 0) != 0:
                    await self._set_output_limit(0)
                    _LOGGER.debug("Zendure: forcing output_limit=0 before switching to AC INPUT")

            await self._set_ac_mode(ac_mode)

            last_mode = self._persist.get("last_set_mode")
            if last_mode != ac_mode:
                _LOGGER.debug("Zendure: AC mode changed, skipping limits this cycle")
            else:
                await self._set_input_limit(in_w)
                await self._set_output_limit(out_w)

            # FINAL EFFECTIVE STATE
            is_charging = ac_mode == ZENDURE_MODE_INPUT and float(in_w) > 0.0
            is_discharging = ac_mode == ZENDURE_MODE_OUTPUT and float(out_w) > 0.0

            # NEXT PLANNED ACTION (transparency)
            planned_action = "none"
            planned_time = None

            if planning.get("status") == "planning_waiting_for_cheap_window" and planning.get("latest_start"):
                planned_action = "charge"
                planned_time = dt_util.parse_datetime(str(planning.get("latest_start")))
            elif planning.get("status") == "planning_charge_now":
                planned_action = "charge"
                planned_time = now

            self._persist["next_planned_action"] = planned_action
            self._persist["next_planned_action_time"] = planned_time.isoformat() if planned_time else None

            # NEXT ACTION TIMESTAMP (V1.3.x)
            if prev_power_state != str(self._persist.get("power_state") or "idle"):
                if self._persist.get("power_state") in ("charging", "discharging"):
                    self._persist["next_action_time"] = dt_util.utcnow().isoformat()
                else:
                    self._persist["next_action_time"] = None

            if not is_charging and not is_discharging:
                recommendation = RECO_STANDBY
                decision_reason = "state_idle"

            # FINAL AI STATUS
            if ai_mode == AI_MODE_MANUAL:
                ai_status = AI_STATUS_MANUAL
            elif self._persist.get("emergency_active"):
                ai_status = AI_STATUS_EMERGENCY_CHARGE
            elif is_charging:
                ai_status = AI_STATUS_CHARGE_SURPLUS
            elif is_discharging:
                if decision_reason.startswith("very_expensive"):
                    ai_status = AI_STATUS_VERY_EXPENSIVE_FORCE
                elif decision_reason == "expensive_discharge":
                    ai_status = AI_STATUS_EXPENSIVE_DISCHARGE
                else:
                    ai_status = AI_STATUS_COVER_DEFICIT
            else:
                ai_status = AI_STATUS_STANDBY

            # Analytics
            last_ts = self._persist.get("last_ts")
            dt_s = 0.0
            if last_ts:
                try:
                    prev_dt = dt_util.parse_datetime(str(last_ts))
                    if prev_dt:
                        dt_s = max((now - prev_dt).total_seconds(), 0.0)
                except Exception:
                    dt_s = 0.0

            in_w_f = float(in_w)
            out_w_f = float(out_w)

            charged_kwh = float(self._persist.get("charged_kwh") or 0.0)
            discharged_kwh = float(self._persist.get("discharged_kwh") or 0.0)
            profit_eur = float(self._persist.get("profit_eur") or 0.0)

            avg_charge_price = self._persist.get("trade_avg_charge_price")
            trade_charged_kwh = float(self._persist.get("trade_charged_kwh") or 0.0)
            prev_soc = self._persist.get("prev_soc")

            SOC_EPS = 0.2
            if (
                prev_soc is not None
                and float(prev_soc) > float(soc_min) + SOC_EPS
                and float(soc) <= float(soc_min) + SOC_EPS
                and ac_mode == ZENDURE_MODE_OUTPUT
                and out_w_f > 0.0
            ):
                avg_charge_price = None
                trade_charged_kwh = 0.0

            if ac_mode == ZENDURE_MODE_INPUT and in_w_f > 0.0:
                e_kwh = (in_w_f * dt_s) / 3600000.0
                charged_kwh += e_kwh

                c_price = price_now
                is_trading_charge = (
                    recommendation == RECO_CHARGE
                    and ai_mode != AI_MODE_MANUAL
                    and decision_reason not in ("emergency_latched_charge", "manual_charge")
                )
                if is_trading_charge and c_price is not None:
                    trade_charged_kwh += e_kwh
                    if avg_charge_price is None:
                        avg_charge_price = float(c_price)
                    else:
                        prev_e = max(trade_charged_kwh - e_kwh, 0.0)
                        avg_charge_price = (
                            (float(avg_charge_price) * prev_e) + (float(c_price) * e_kwh)
                        ) / max(trade_charged_kwh, 1e-9)

            if ac_mode == ZENDURE_MODE_OUTPUT and out_w_f > 0.0:
                e_kwh = (out_w_f * dt_s) / 3600000.0
                discharged_kwh += e_kwh
                if price_now is not None and avg_charge_price is not None:
                    delta = float(price_now) - float(avg_charge_price)
                    if delta > 0:
                        profit_eur += e_kwh * delta

            self._persist["trade_avg_charge_price"] = avg_charge_price
            self._persist["trade_charged_kwh"] = trade_charged_kwh
            self._persist["prev_soc"] = float(soc)
            self._persist["avg_charge_price"] = avg_charge_price

            self._persist["charged_kwh"] = charged_kwh
            self._persist["discharged_kwh"] = discharged_kwh
            self._persist["profit_eur"] = profit_eur
            self._persist["last_ts"] = now.isoformat()

            await self._save()

            details = {
                "soc": soc,
                "pv_w": pv_w,
                "surplus": float(surplus),
                "deficit": float(deficit_raw),
                "house_load": int(round(house_load, 0)),
                "price_now": price_now,
                "expensive_threshold": expensive,
                "very_expensive_threshold": very_expensive,
                "emergency_soc": emergency_soc,
                "emergency_charge_w": emergency_w,
                "emergency_active": bool(self._persist.get("emergency_active")),
                "power_state": str(self._persist.get("power_state") or "idle"),

                "next_action_state": (
                    "manual_charge" if ai_mode == AI_MODE_MANUAL and manual_action == MANUAL_CHARGE else
                    "manual_discharge" if ai_mode == AI_MODE_MANUAL and manual_action == MANUAL_DISCHARGE else
                    "emergency_charge" if self._persist.get("emergency_active") else
                    "charging_active" if self._persist.get("power_state") == "charging" else
                    "discharging_active" if self._persist.get("power_state") == "discharging" else
                    "none"
                ),

                "next_planned_action": self._persist.get("next_planned_action"),
                "next_planned_action_time": self._persist.get("next_planned_action_time"),

                "next_action_time": self._persist.get("next_action_time"),

                "planning_checked": bool(self._persist.get("planning_checked")),
                "planning_status": self._persist.get("planning_status"),
                "planning_blocked_by": self._persist.get("planning_blocked_by"),
                "planning_active": bool(self._persist.get("planning_active")),
                "planning_target_soc": self._persist.get("planning_target_soc"),
                "planning_next_peak": self._persist.get("planning_next_peak"),
                "planning_reason": self._persist.get("planning_reason"),

                "max_charge": max_charge,
                "max_discharge": max_discharge,

                "set_mode": ac_mode,
                "set_input_w": int(round(in_w_f, 0)),
                "set_output_w": int(round(out_w_f, 0)),

                "avg_charge_price": avg_charge_price,
                "charged_kwh": charged_kwh,
                "discharged_kwh": discharged_kwh,
                "profit_eur": profit_eur,

                "profit_margin_pct": profit_margin_pct,

                "ai_mode": ai_mode,
                "manual_action": manual_action,
                "decision_reason": decision_reason,
            }

            return {
                "status": status,
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK" if status == STATUS_OK else str(status).upper(),
                "details": details,
                "decision_reason": decision_reason,
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err