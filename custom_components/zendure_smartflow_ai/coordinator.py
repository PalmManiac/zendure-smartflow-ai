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
    # config keys
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
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
    # settings keys
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_VERY_EXPENSIVE_THRESHOLD,
    SETTING_PROFIT_MARGIN_PERCENT,
    # defaults
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_PROFIT_MARGIN_PERCENT,
    # runtime selects
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
    # enums
    STATUS_INIT,
    STATUS_OK,
    STATUS_SENSOR_INVALID,
    STATUS_PRICE_MISSING,
    RECO_STANDBY,
    RECO_CHARGE,
    RECO_DISCHARGE,
    AI_STATUS_STANDBY,
    AI_STATUS_CHARGE_SURPLUS,
    AI_STATUS_COVER_DEFICIT,
    AI_STATUS_VERY_EXPENSIVE,
    AI_STATUS_PROFIT_MARGIN,
    AI_STATUS_MANUAL,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY_FMT = "zendure_smartflow_ai_v013_{entry_id}"


@dataclass
class EntityIds:
    soc: str
    pv: str

    price_now: str | None
    price_export: str | None

    grid_mode: str
    grid_power: str | None
    grid_import: str | None
    grid_export: str | None

    ac_mode: str
    input_limit: str
    output_limit: str


def _to_float(val: Any, default: float | None = None) -> float | None:
    try:
        if val is None:
            return default
        return float(str(val).replace(",", "."))
    except Exception:
        return default


def _state_is_bad(val: Any) -> bool:
    if val is None:
        return True
    s = str(val).lower()
    return s in ("unknown", "unavailable", "")


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    v0.13.0:
    - House load computed internally from grid + PV
    - Persisted avg charge price and cumulative profit
    - Profit-margin based discharge in winter/automatic
    - Very-expensive threshold remains hard override
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry

        data = entry.data

        self.entities = EntityIds(
            soc=data[CONF_SOC_ENTITY],
            pv=data[CONF_PV_ENTITY],
            price_now=data.get(CONF_PRICE_NOW_ENTITY),
            price_export=data.get(CONF_PRICE_EXPORT_ENTITY),
            grid_mode=data.get(CONF_GRID_MODE, GRID_MODE_NONE),
            grid_power=data.get(CONF_GRID_POWER_ENTITY),
            grid_import=data.get(CONF_GRID_IMPORT_ENTITY),
            grid_export=data.get(CONF_GRID_EXPORT_ENTITY),
            ac_mode=data[CONF_AC_MODE_ENTITY],
            input_limit=data[CONF_INPUT_LIMIT_ENTITY],
            output_limit=data[CONF_OUTPUT_LIMIT_ENTITY],
        )

        # runtime selects
        self.runtime_mode: dict[str, str] = {
            "ai_mode": AI_MODE_AUTOMATIC,
            "manual_action": MANUAL_STANDBY,
        }

        # settings (Number entities live in HA; coordinator reads them via states)
        self.settings_entities: dict[str, str] = {
            SETTING_SOC_MIN: f"number.{DOMAIN}_{SETTING_SOC_MIN}",
            SETTING_SOC_MAX: f"number.{DOMAIN}_{SETTING_SOC_MAX}",
            SETTING_MAX_CHARGE: f"number.{DOMAIN}_{SETTING_MAX_CHARGE}",
            SETTING_MAX_DISCHARGE: f"number.{DOMAIN}_{SETTING_MAX_DISCHARGE}",
            SETTING_VERY_EXPENSIVE_THRESHOLD: f"number.{DOMAIN}_{SETTING_VERY_EXPENSIVE_THRESHOLD}",
            SETTING_PROFIT_MARGIN_PERCENT: f"number.{DOMAIN}_{SETTING_PROFIT_MARGIN_PERCENT}",
        }

        # persisted storage
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY_FMT.format(entry_id=entry.entry_id))
        self._persist: dict[str, float] = {
            "total_charge_kwh": 0.0,
            "total_charge_cost": 0.0,
            "total_profit_eur": 0.0,
        }

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def async_config_entry_first_refresh(self) -> None:
        await self._load_persisted()
        await super().async_config_entry_first_refresh()

    async def _load_persisted(self) -> None:
        try:
            loaded = await self._store.async_load()
            if isinstance(loaded, dict):
                for k in ("total_charge_kwh", "total_charge_cost", "total_profit_eur"):
                    if k in loaded and isinstance(loaded[k], (int, float)):
                        self._persist[k] = float(loaded[k])
        except Exception as err:
            _LOGGER.debug("Persist load failed: %s", err)

    async def _save_persisted(self) -> None:
        try:
            await self._store.async_save(self._persist)
        except Exception as err:
            _LOGGER.debug("Persist save failed: %s", err)

    # -------------------------------
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

    # -------------------------------
    def _get_price_now(self) -> float | None:
        # direct sensor first
        if self.entities.price_now:
            v = self._to_price(self._state(self.entities.price_now))
            if v is not None:
                return v

        # export list
        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list) or not export:
            return None

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        if idx < 0 or idx >= len(export):
            return None

        try:
            item = export[idx]
            if isinstance(item, dict):
                return self._to_price(item.get("price_per_kwh"))
        except Exception:
            return None
        return None

    @staticmethod
    def _to_price(val: Any) -> float | None:
        v = _to_float(val, None)
        if v is None:
            return None
        # ignore absurd values
        if v < 0 or v > 5:
            return None
        return float(v)

    # -------------------------------
    def _compute_grid(self) -> tuple[float | None, float | None]:
        """
        Returns (grid_import_w, grid_export_w)
        """
        mode = self.entities.grid_mode or GRID_MODE_NONE

        if mode == GRID_MODE_SPLIT:
            imp = _to_float(self._state(self.entities.grid_import), None)
            exp = _to_float(self._state(self.entities.grid_export), None)
            if imp is None or exp is None:
                return None, None
            return max(imp, 0.0), max(exp, 0.0)

        if mode == GRID_MODE_SINGLE:
            p = _to_float(self._state(self.entities.grid_power), None)
            if p is None:
                return None, None
            if p >= 0:
                return float(p), 0.0
            return 0.0, float(abs(p))

        return None, None

    # -------------------------------
    def _read_setting(self, key: str, default: float) -> float:
        ent = self.settings_entities.get(key)
        v = _to_float(self._state(ent), None)
        return float(v) if v is not None else float(default)

    # -------------------------------
    async def _set_ac_mode(self, mode: str) -> None:
        # Zendure select expects options like "input"/"output" (lowercase)
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
            {"entity_id": self.entities.input_limit, "value": int(round(max(watts, 0.0), 0))},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": int(round(max(watts, 0.0), 0))},
            blocking=False,
        )

    # -------------------------------
    def _avg_charge_price(self) -> float | None:
        kwh = self._persist.get("total_charge_kwh", 0.0)
        cost = self._persist.get("total_charge_cost", 0.0)
        if kwh <= 0.0001:
            return None
        return cost / kwh

    # -------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc_raw = self._state(self.entities.soc)
            pv_raw = self._state(self.entities.pv)

            soc = _to_float(soc_raw, None)
            pv = _to_float(pv_raw, None)

            if soc is None or pv is None or _state_is_bad(soc_raw) or _state_is_bad(pv_raw):
                return {
                    "status": STATUS_SENSOR_INVALID,
                    "ai_status": AI_STATUS_STANDBY,
                    "recommendation": RECO_STANDBY,
                    "debug": "SENSOR_INVALID",
                    "details": {
                        "soc_raw": soc_raw,
                        "pv_raw": pv_raw,
                    },
                }

            grid_imp, grid_exp = self._compute_grid()

            # compute house load if grid is available, else None
            load = None
            if grid_imp is not None and grid_exp is not None:
                load = max(float(pv) + float(grid_imp) - float(grid_exp), 0.0)

            price_now = self._get_price_now()
            avg_charge_price = self._avg_charge_price()

            # settings
            soc_min = self._read_setting(SETTING_SOC_MIN, DEFAULT_SOC_MIN)
            soc_max = self._read_setting(SETTING_SOC_MAX, DEFAULT_SOC_MAX)
            max_charge = self._read_setting(SETTING_MAX_CHARGE, DEFAULT_MAX_CHARGE)
            max_discharge = self._read_setting(SETTING_MAX_DISCHARGE, DEFAULT_MAX_DISCHARGE)
            very_expensive = self._read_setting(SETTING_VERY_EXPENSIVE_THRESHOLD, DEFAULT_VERY_EXPENSIVE_THRESHOLD)
            profit_margin_pct = self._read_setting(SETTING_PROFIT_MARGIN_PERCENT, DEFAULT_PROFIT_MARGIN_PERCENT)

            ai_mode = self.runtime_mode.get("ai_mode", AI_MODE_AUTOMATIC)
            manual_action = self.runtime_mode.get("manual_action", MANUAL_STANDBY)

            # derived
            surplus = None
            deficit = None
            if load is not None:
                surplus = max(float(pv) - float(load), 0.0)
            if grid_imp is not None:
                deficit = float(grid_imp)

            # defaults (no action)
            status = STATUS_OK
            ai_status = AI_STATUS_STANDBY
            recommendation = RECO_STANDBY

            set_mode = "input"
            set_in_w = 0.0
            set_out_w = 0.0

            reason = "standby"

            # ==========================================================
            # 1) MANUAL overrides everything
            # ==========================================================
            if ai_mode == AI_MODE_MANUAL:
                ai_status = AI_STATUS_MANUAL
                if manual_action == MANUAL_CHARGE and soc < soc_max:
                    recommendation = RECO_CHARGE
                    set_mode = "input"
                    set_in_w = max_charge
                    reason = "manual_charge"
                elif manual_action == MANUAL_DISCHARGE and soc > soc_min and deficit is not None:
                    recommendation = RECO_DISCHARGE
                    set_mode = "output"
                    set_out_w = min(max_discharge, deficit)
                    reason = "manual_discharge_cover_deficit"
                else:
                    recommendation = RECO_STANDBY
                    set_mode = "input"
                    reason = "manual_standby_or_limits"

            else:
                # ======================================================
                # 2) VERY EXPENSIVE override (needs price and deficit)
                # ======================================================
                if price_now is not None and deficit is not None and price_now >= very_expensive and soc > soc_min:
                    ai_status = AI_STATUS_VERY_EXPENSIVE
                    recommendation = RECO_DISCHARGE
                    set_mode = "output"
                    set_out_w = min(max_discharge, deficit)
                    reason = "very_expensive_cover_deficit"

                # ======================================================
                # 3) SUMMER mode - PV surplus charge + cover deficit later
                # ======================================================
                elif ai_mode == AI_MODE_SUMMER:
                    if surplus is not None and surplus > 80 and soc < soc_max:
                        ai_status = AI_STATUS_CHARGE_SURPLUS
                        recommendation = RECO_CHARGE
                        set_mode = "input"
                        set_in_w = min(max_charge, surplus)
                        reason = "summer_charge_surplus"
                    elif deficit is not None and deficit > 30 and soc > soc_min:
                        ai_status = AI_STATUS_COVER_DEFICIT
                        recommendation = RECO_DISCHARGE
                        set_mode = "output"
                        set_out_w = min(max_discharge, deficit)
                        reason = "summer_cover_deficit"
                    else:
                        reason = "summer_standby"

                # ======================================================
                # 4) WINTER / AUTOMATIC - profit margin logic
                # ======================================================
                else:
                    # Charge from PV surplus (always allowed, no price required)
                    if surplus is not None and surplus > 80 and soc < soc_max:
                        ai_status = AI_STATUS_CHARGE_SURPLUS
                        recommendation = RECO_CHARGE
                        set_mode = "input"
                        set_in_w = min(max_charge, surplus)
                        reason = "charge_surplus"
                    else:
                        # Discharge only if we have:
                        # - deficit, soc>min, price available
                        # - AND avg charge price available and margin reached
                        if deficit is not None and deficit > 30 and soc > soc_min and price_now is not None and avg_charge_price is not None:
                            target = avg_charge_price * (1.0 + (profit_margin_pct / 100.0))
                            if price_now >= target:
                                ai_status = AI_STATUS_PROFIT_MARGIN
                                recommendation = RECO_DISCHARGE
                                set_mode = "output"
                                set_out_w = min(max_discharge, deficit)
                                reason = "profit_margin_reached"
                            else:
                                reason = "profit_margin_not_reached"
                        else:
                            if price_now is None:
                                status = STATUS_PRICE_MISSING
                                reason = "price_missing"
                            elif avg_charge_price is None:
                                reason = "avg_charge_price_missing"
                            elif deficit is None:
                                reason = "grid_missing"
                            else:
                                reason = "standby"

            # ==========================================================
            # Apply hardware setpoints
            # - standby = 0/0 (keep mode input)
            # ==========================================================
            if recommendation == RECO_STANDBY:
                set_mode = "input"
                set_in_w = 0.0
                set_out_w = 0.0

            await self._set_ac_mode(set_mode)
            await self._set_input_limit(set_in_w)
            await self._set_output_limit(set_out_w)

            # ==========================================================
            # Persist tracking (only when price exists)
            # - charge: record cost-weighted energy when we actually command charging
            # - discharge: record profit when discharging to cover deficit
            # ==========================================================
            interval_h = UPDATE_INTERVAL / 3600.0
            energy_kwh = 0.0

            if price_now is not None:
                # Charging tracking (assume grid charge only if we are charging and there is grid import)
                if recommendation == RECO_CHARGE and set_in_w > 0:
                    # If grid is available and importing, we assume price-relevant energy
                    if deficit is not None and deficit > 0:
                        energy_kwh = (set_in_w * interval_h) / 1000.0
                        self._persist["total_charge_kwh"] += energy_kwh
                        self._persist["total_charge_cost"] += energy_kwh * price_now

                # Profit tracking on discharge (only if avg available)
                avg_now = self._avg_charge_price()
                if recommendation == RECO_DISCHARGE and set_out_w > 0 and avg_now is not None:
                    energy_kwh = (set_out_w * interval_h) / 1000.0
                    avoided = energy_kwh * price_now
                    cost_basis = energy_kwh * avg_now
                    self._persist["total_profit_eur"] += (avoided - cost_basis)

                await self._save_persisted()

            # Build details
            details = {
                "mode": ai_mode,
                "manual_action": manual_action,
                "reason": reason,
                "soc": float(soc),
                "soc_min": soc_min,
                "soc_max": soc_max,
                "pv": float(pv),
                "grid_import": grid_imp,
                "grid_export": grid_exp,
                "load": load,
                "surplus": surplus,
                "deficit": deficit,
                "price_now": price_now,
                "very_expensive_threshold": very_expensive,
                "profit_margin_percent": profit_margin_pct,
                "avg_charge_price": avg_charge_price,
                "avg_target_price": (avg_charge_price * (1.0 + profit_margin_pct / 100.0)) if avg_charge_price is not None else None,
                "total_charge_kwh": self._persist.get("total_charge_kwh", 0.0),
                "total_charge_cost": self._persist.get("total_charge_cost", 0.0),
                "total_profit_eur": self._persist.get("total_profit_eur", 0.0),
                "set_mode": set_mode,
                "set_input_w": int(round(set_in_w, 0)),
                "set_output_w": int(round(set_out_w, 0)),
                "entities": {
                    "soc": self.entities.soc,
                    "pv": self.entities.pv,
                    "price_now": self.entities.price_now,
                    "price_export": self.entities.price_export,
                    "grid_mode": self.entities.grid_mode,
                    "grid_power": self.entities.grid_power,
                    "grid_import": self.entities.grid_import,
                    "grid_export": self.entities.grid_export,
                    "ac_mode": self.entities.ac_mode,
                    "input_limit": self.entities.input_limit,
                    "output_limit": self.entities.output_limit,
                },
            }

            return {
                "status": status,
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK" if status == STATUS_OK else status.upper(),
                "details": details,
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
