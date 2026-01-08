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

            # emergency latch
            "emergency_active": False,

            # --- V1.2 price planning ---
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
            "profit_eur": 0.0,
            "last_ts": None,
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
        """Price planning based on *peak average* and profit margin.

        Logic (as discussed):
        - Search upcoming prices for a peak (use maximum in horizon).
        - Compute average of the peak segment (>= 90% of the peak).
        - Compute target price = peak_avg * (1 - margin).
        - If there is no slot before the peak below target: do nothing.
        - If current price <= target: plan/charge now (limited by max_charge).
        - If peak is very near (<= 4 slots) and price is still below peak_avg: last chance charge.
        """
        result: dict[str, Any] = {
            "action": "none",
            "watts": 0.0,
            "status": "not_checked",
            "blocked_by": None,
            "next_peak": None,
            "reason": None,
        }

        if ai_mode != AI_MODE_AUTOMATIC:
            result.update(
                status="planning_inactive_mode",
                blocked_by="mode",
                reason=f"inactive_mode(mode={ai_mode})",
            )
            return result

        if float(soc) >= float(soc_max) - 0.1:
            result.update(
                status="planning_blocked_soc_full",
                blocked_by="soc",
                reason=f"soc_full(soc={float(soc):.1f}>=soc_max={float(soc_max):.1f})",
            )
            return result

        if price_now is None:
            result.update(
                status="planning_no_price_now",
                blocked_by="price_now",
                reason="price_now_missing",
            )
            return result

        if not self.entities.price_export:
            result.update(
                status="planning_no_price_data",
                blocked_by="price_data",
                reason="price_export_entity_missing",
            )
            return result

        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list):
            result.update(
                status="planning_no_price_data",
                blocked_by="price_data",
                reason="price_export_data_not_list",
            )
            return result

        future_prices: list[float] = []
        for item in export:
            if not isinstance(item, dict):
                result.update(
                    status="planning_no_price_data",
                    blocked_by="price_data",
                    reason="price_export_item_not_dict",
                )
                return result
            p = _to_float(item.get("price_per_kwh"), None)
            if p is None:
                result.update(
                    status="planning_no_price_data",
                    blocked_by="price_data",
                    reason="price_export_price_per_kwh_missing",
                )
                return result
            future_prices.append(float(p))

        if len(future_prices) < 8:
            result.update(
                status="planning_no_price_data",
                blocked_by="price_data",
                reason="future_prices_too_short",
            )
            return result

        margin = max(float(profit_margin_pct or 0.0), 0.0) / 100.0

        peak_rel_idx = int(max(range(len(future_prices)), key=lambda i: float(future_prices[i])))
        peak_price = float(future_prices[peak_rel_idx])

        pre_peak = future_prices[:peak_rel_idx]
        if len(pre_peak) < 4:
            result.update(
                status="planning_peak_detected_insufficient_window",
                blocked_by="price_data",
                reason="peak_found_but_pre_peak_window_too_short",
            )
            return result

        seg_thr = peak_price * 0.90
        seg_prices: list[float] = []
        j = peak_rel_idx
        while j < len(future_prices) and float(future_prices[j]) >= seg_thr:
            seg_prices.append(float(future_prices[j]))
            j += 1

        peak_avg = sum(seg_prices) / max(len(seg_prices), 1)
        target_price = peak_avg * (1.0 - margin)

        if peak_avg < float(expensive) and peak_price < float(very_expensive):
            result.update(
                status="planning_no_peak_detected",
                blocked_by=None,
                reason=f"peak_below_thresholds(peak_avg={peak_avg:.4f})",
                next_peak=None,
            )
            return result

        cheap_slots = [float(p) for p in pre_peak if float(p) <= float(target_price)]
        if not cheap_slots:
            result.update(
                status="planning_waiting_for_cheap_window",
                blocked_by="price_data",
                reason=f"no_charge_window_below_target(target={target_price:.4f}, peak_avg={peak_avg:.4f})",
                next_peak={
                    "peak_price": peak_price,
                    "peak_avg": peak_avg,
                    "peak_in_slots": peak_rel_idx,
                    "target_price": target_price,
                },
            )
            return result

        next_peak = {
            "peak_price": peak_price,
            "peak_avg": peak_avg,
            "peak_in_slots": peak_rel_idx,
            "target_price": target_price,
            "cheap_threshold": min(cheap_slots),
        }

        if float(price_now) <= float(target_price):
            watts = max(float(max_charge), 0.0)
            result.update(
                action="charge",
                watts=watts,
                status="planning_charge_now",
                reason=(
                    f"planning_charge_now(price={float(price_now):.4f}<=target={float(target_price):.4f}, "
                    f"peak_avg={float(peak_avg):.4f})"
                ),
                next_peak=next_peak,
            )
            return result

        if peak_rel_idx <= 4 and float(price_now) < float(peak_avg):
            watts = max(float(max_charge), 0.0)
            result.update(
                action="charge",
                watts=watts,
                status="planning_last_chance",
                reason=(
                    f"planning_last_chance(peak_in_slots={peak_rel_idx}, "
                    f"price={float(price_now):.4f}<peak_avg={float(peak_avg):.4f})"
                ),
                next_peak=next_peak,
            )
            return result

        result.update(
            action="none",
            watts=0.0,
            status="planning_waiting_for_cheap_window",
            reason=f"waiting_for_target_window(price={float(price_now):.4f}>target={float(target_price):.4f})",
            next_peak=next_peak,
        )
        return result

    # --------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            if self._persist.get("last_ts") is None:
                await self._load()
                self._persist["last_ts"] = dt_util.utcnow().isoformat()

            now = dt_util.utcnow()

            soc = _to_float(self._state(self.entities.soc), None)
            pv = _to_float(self._state(self.entities.pv), None)

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
            very_expensive = self._get_setting(
                SETTING_VERY_EXPENSIVE_THRESHOLD, DEFAULT_VERY_EXPENSIVE_THRESHOLD
            )
            emergency_soc = self._get_setting(SETTING_EMERGENCY_SOC, DEFAULT_EMERGENCY_SOC)
            emergency_w = self._get_setting(SETTING_EMERGENCY_CHARGE, DEFAULT_EMERGENCY_CHARGE)
            profit_margin_pct = self._get_setting(
                SETTING_PROFIT_MARGIN_PCT, DEFAULT_PROFIT_MARGIN_PCT
            )

            ai_mode = self.runtime_mode.get("ai_mode", AI_MODE_AUTOMATIC)
            manual_action = self.runtime_mode.get("manual_action", MANUAL_STANDBY)

            deficit, surplus = self._get_grid()
            price_now = self._get_price_now()
            
			# --------------------------------------------------
			# FIX 3: Ignore battery feed-in as PV surplus
			# If price logic wants discharge, any feed-in is NOT PV
			# --------------------------------------------------
			if surplus is not None and surplus > 0:
                if (
                    price_now is not None
                    and (
                        price_now >= expensive
                        or price_now >= very_expensive
                    )
                    and soc > soc_min
                ):
                    surplus = None
            
            # Emergency latch
            if soc <= emergency_soc:
                self._persist["emergency_active"] = True
            if self._persist.get("emergency_active") and soc >= soc_min:
                self._persist["emergency_active"] = False

            status = STATUS_OK
            ai_status = AI_STATUS_STANDBY
            recommendation = RECO_STANDBY
            ac_mode = ZENDURE_MODE_INPUT
            in_w = 0.0
            out_w = 0.0
            decision_reason = "idle"

            # reset planning flags each cycle
            self._persist["planning_checked"] = False
            self._persist["planning_status"] = "not_checked"
            self._persist["planning_blocked_by"] = None
            self._persist["planning_active"] = False
            self._persist["planning_reason"] = None
            self._persist["planning_target_soc"] = None
            self._persist["planning_next_peak"] = None

            # Emergency charge (latched)
            if self._persist.get("emergency_active"):
                ai_status = AI_STATUS_EMERGENCY_CHARGE
                recommendation = RECO_EMERGENCY
                ac_mode = ZENDURE_MODE_INPUT
                in_w = min(max_charge, max(emergency_w, 0.0))
                out_w = 0.0
                decision_reason = "emergency_latched_charge"

            else:
                # Manual mode
                if ai_mode == AI_MODE_MANUAL:
                    ai_status = AI_STATUS_MANUAL
                    decision_reason = "manual_mode"

                    if manual_action == MANUAL_STANDBY:
                        recommendation = RECO_STANDBY
                        ac_mode = ZENDURE_MODE_INPUT
                        in_w = 0.0
                        out_w = 0.0

                    elif manual_action == MANUAL_CHARGE:
                        recommendation = RECO_CHARGE
                        ac_mode = ZENDURE_MODE_INPUT
                        in_w = min(max_charge, max_charge)
                        out_w = 0.0
                        decision_reason = "manual_charge"
                        
                        # >>> MANUAL CHARGE IS ABSOLUTE <<<
                        await self._set_ac_mode(ac_mode)
                        await self._set_input_limit(in_w)
                        await self._set_output_limit(out_w)

                        await self._save()

                        return {
                            "status": status,
                            "ai_status": AI_STATUS_MANUAL,
                            "recommendation": recommendation,
                            "debug": "OK",
                            "details": {},
                            "decision_reason": decision_reason,
                        }    

                    elif manual_action == MANUAL_DISCHARGE:
                        recommendation = RECO_DISCHARGE
                        ac_mode = ZENDURE_MODE_OUTPUT
                        in_w = 0.0
                        target = deficit if deficit is not None else max_discharge
                        out_w = min(max_discharge, max(float(target or 0.0), 0.0))
                        decision_reason = "manual_discharge"

                else:
                    is_summer = ai_mode == AI_MODE_SUMMER
                    is_winter = ai_mode == AI_MODE_WINTER

                    # --------------------------------------------------
                    # FIX 2: Block PV logic during active discharge
                    # Prevent charge/discharge oscillation
                    # --------------------------------------------------
                    if recommendation == RECO_DISCHARGE or ac_mode == ZENDURE_MODE_OUTPUT:
                        surplus = None

                    # planning (automatic only)
                    planning_applied = False
                    if ai_mode == AI_MODE_AUTOMATIC:
                        self._persist["planning_checked"] = True
                        planning = self._evaluate_price_planning(
                            soc=soc,
                            soc_max=float(soc_max),
                            price_now=price_now,
                            expensive=float(expensive),
                            very_expensive=float(very_expensive),
                            profit_margin_pct=float(profit_margin_pct),
                            max_charge=float(max_charge),
                            surplus_w=surplus,
                            ai_mode=ai_mode,
                        )
                        self._persist["planning_status"] = planning.get("status")
                        self._persist["planning_blocked_by"] = planning.get("blocked_by")
                        self._persist["planning_reason"] = planning.get("reason")
                        self._persist["planning_next_peak"] = planning.get("next_peak")
                        self._persist["planning_active"] = planning.get("action") == "charge"

                        # In main logic, before applying planning charge
                        if planning.get("action") == "charge":
                            planning_applied = True
                            ai_status = AI_STATUS_STANDBY
                            recommendation = RECO_CHARGE
                            ac_mode = ZENDURE_MODE_INPUT
                            in_w = min(max_charge, float(planning.get("watts") or max_charge))
                            out_w = 0.0
                            decision_reason = str(planning.get("reason"))
                            
                    if not planning_applied:
                        decision_reason = "automatic_idle"

                        # VERY EXPENSIVE always has absolute priority
                        if price_now is not None and price_now >= very_expensive and soc > (soc_min + 0.2):
                            ai_status = AI_STATUS_VERY_EXPENSIVE_FORCE
                            recommendation = RECO_DISCHARGE
                            ac_mode = ZENDURE_MODE_OUTPUT
                            in_w = 0.0

                            needed_w = 0.0
                            if deficit is not None and deficit > 0:
                                needed_w = float(deficit)

                            out_w = min(needed_w, 2400.0)
                            decision_reason = "very_expensive_force_discharge_unlimited"
                            
                        # summer: cover deficit if possible
                        elif is_summer and deficit is not None and deficit > 0 and soc > soc_min:
                            ai_status = AI_STATUS_COVER_DEFICIT
                            recommendation = RECO_DISCHARGE
                            ac_mode = ZENDURE_MODE_OUTPUT
                            in_w = 0.0
                            # prefer slight feed-in over grid import
                            target = deficit if deficit is not None else max_discharge
                            out_w = min(max_discharge, max(target + 50.0, 0.0))
                            decision_reason = "summer_cover_deficit"

                        # PV surplus charge (ONLY if not discharging)
                        elif (
                            surplus is not None
                            and surplus > 50
                            and soc < soc_max
                            and ac_mode != ZENDURE_MODE_OUTPUT
                            and recommendation != RECO_DISCHARGE
                        ):
                            ai_status = AI_STATUS_CHARGE_SURPLUS
                            recommendation = RECO_CHARGE
                            ac_mode = ZENDURE_MODE_INPUT
                            in_w = min(max_charge, float(surplus))
                            out_w = 0.0
                            decision_reason = "pv_surplus_charge"

                        # winter: cover deficit if possible
                        elif is_winter and deficit is not None and deficit > 0 and soc > soc_min:
                            ai_status = AI_STATUS_COVER_DEFICIT
                            recommendation = RECO_DISCHARGE
                            ac_mode = ZENDURE_MODE_OUTPUT
                            in_w = 0.0
                            # prefer slight feed-in over grid import
                            target = deficit if deficit is not None else max_discharge
                            out_w = min(max_discharge, max(target + 50.0, 0.0))
                            decision_reason = "cover_deficit"

                        elif (
                            price_now is not None
                            and price_now >= expensive
                            and price_now < very_expensive
                            and soc > soc_min
                            and deficit is not None
                            and deficit > 0
                        ):

                            ai_status = AI_STATUS_EXPENSIVE_DISCHARGE
                            recommendation = RECO_DISCHARGE
                            ac_mode = ZENDURE_MODE_OUTPUT
                            in_w = 0.0
                            # prefer slight feed-in over grid import
                            target = deficit if deficit is not None else max_discharge
                            out_w = min(max_discharge, max(target + 50.0, 0.0))
                            decision_reason = "expensive_discharge"

                        if recommendation == RECO_STANDBY:
                            ai_status = AI_STATUS_STANDBY
                            ac_mode = ZENDURE_MODE_INPUT
                            in_w = 0.0
                            out_w = 0.0
                            decision_reason = "standby_no_condition_met"

            # enforce SoC-min on discharge
            if ac_mode == ZENDURE_MODE_OUTPUT and soc <= soc_min:
                ac_mode = ZENDURE_MODE_INPUT
                out_w = 0.0
                if recommendation == RECO_DISCHARGE:
                    recommendation = RECO_STANDBY

            # Apply hardware setpoints
            if ac_mode == ZENDURE_MODE_OUTPUT:
                in_w = 0.0
            if ac_mode == ZENDURE_MODE_INPUT:
                out_w = 0.0

            await self._set_ac_mode(ac_mode)
            await self._set_input_limit(in_w)
            await self._set_output_limit(out_w)

            # --------------------------------------------------
            # FINAL AI STATUS (derived from actual action)
            # --------------------------------------------------
            if ac_mode == ZENDURE_MODE_INPUT and in_w > 0:
                if decision_reason == "pv_surplus_charge":
                    ai_status = AI_STATUS_CHARGE_SURPLUS
                else:
                    ai_status = AI_STATUS_STANDBY

            elif ac_mode == ZENDURE_MODE_OUTPUT and out_w > 0:
                if decision_reason.startswith("very_expensive"):
                    ai_status = AI_STATUS_VERY_EXPENSIVE_FORCE
                elif decision_reason == "expensive_discharge":
                    ai_status = AI_STATUS_EXPENSIVE_DISCHARGE
                else:
                    ai_status = AI_STATUS_COVER_DEFICIT

            else:
                ai_status = AI_STATUS_STANDBY

            # --- house load calculation (total house consumption) ---
            house_load = 0.0

            # PV contribution
            if pv is not None:
                house_load = float(pv)

            # subtract feed-in (surplus)
            if surplus is not None and surplus > 0:
                house_load -= float(surplus)

            # add grid import
            if deficit is not None and deficit > 0:
                house_load += float(deficit)

            house_load = max(house_load, 0.0)

            # Analytics
            last_ts = self._persist.get("last_ts")
            if last_ts:
                try:
                    prev = dt_util.parse_datetime(str(last_ts))
                except Exception:
                    prev = None
            else:
                prev = None

            if prev is None:
                dt_s = 0.0
            else:
                dt_s = max((now - prev).total_seconds(), 0.0)

            in_w = float(in_w)
            out_w = float(out_w)

            charged_kwh = float(self._persist.get("charged_kwh") or 0.0)
            discharged_kwh = float(self._persist.get("discharged_kwh") or 0.0)
            profit_eur = float(self._persist.get("profit_eur") or 0.0)

            # --- Trading analytics (exclude emergency/manual charges) ---
            avg_charge_price = self._persist.get("trade_avg_charge_price")
            trade_charged_kwh = float(self._persist.get("trade_charged_kwh") or 0.0)
            prev_soc = self._persist.get("prev_soc")

            # Reset trading average when battery reaches SoC-Min by discharge (cycle finished)
            SOC_EPS = 0.2
            if (
                prev_soc is not None
                and float(prev_soc) > float(soc_min) + SOC_EPS
                and float(soc) <= float(soc_min) + SOC_EPS
                and ac_mode == ZENDURE_MODE_OUTPUT
                and out_w > 0
            ):
                avg_charge_price = None
                trade_charged_kwh = 0.0

            if ac_mode == ZENDURE_MODE_INPUT and in_w > 0:
                e_kwh = (in_w * dt_s) / 3600000.0
                charged_kwh += e_kwh

                # PV-Laden zählt als "0"
                if decision_reason == "pv_surplus_charge":
                    c_price = 0.0
                else:
                    c_price = price_now

                # Trading-Ladungen: nur normale CHARGE (nicht Notladung, nicht manuell)
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

            if ac_mode == ZENDURE_MODE_OUTPUT and out_w > 0:
                e_kwh = (out_w * dt_s) / 3600000.0
                discharged_kwh += e_kwh

                if price_now is not None and avg_charge_price is not None:
                    delta = float(price_now) - float(avg_charge_price)
                    if delta > 0:
                        profit_eur += e_kwh * delta

            # Persist trading analytics + expose avg_charge_price as trading-only average
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
                "pv_w": pv,
                "surplus": surplus,
                "deficit": deficit,
                "house_load": int(round(house_load, 0)),
                "price_now": price_now,
                "expensive_threshold": expensive,
                "very_expensive_threshold": very_expensive,
                "emergency_soc": emergency_soc,
                "emergency_charge_w": emergency_w,
                "emergency_active": bool(self._persist.get("emergency_active")),

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
                "set_input_w": int(round(in_w, 0)),
                "set_output_w": int(round(out_w, 0)),

                "avg_charge_price": avg_charge_price,
                "charged_kwh": charged_kwh,
                "discharged_kwh": discharged_kwh,
                "profit_eur": profit_eur,

                "profit_margin_pct": profit_margin_pct,

                "ai_mode": ai_mode,
                "manual_action": manual_action,
            }

            return {
                "status": status,
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK" if status == STATUS_OK else status.upper(),
                "details": details,
                "decision_reason": decision_reason,
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
