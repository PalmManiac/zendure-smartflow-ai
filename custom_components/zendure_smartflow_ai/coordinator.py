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

    # modes
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,

    # settings keys
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD,
    SETTING_VERY_EXPENSIVE_THRESHOLD,
    SETTING_EMERGENCY_SOC,
    SETTING_EMERGENCY_CHARGE_W,
    SETTING_PROFIT_MARGIN_PCT,

    # defaults
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_EMERGENCY_SOC,
    DEFAULT_EMERGENCY_CHARGE_W,
    DEFAULT_PROFIT_MARGIN_PCT,

    # statuses
    STATUS_OK,
    STATUS_SENSOR_INVALID,
    STATUS_PRICE_INVALID,

    AI_STATUS_STANDBY,
    AI_STATUS_CHARGE_SURPLUS,
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


@dataclass
class EntityIds:
    soc: str
    pv: str

    price_export: str | None
    price_now: str | None

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
        s = str(val).replace(",", ".").strip()
        if s.lower() in ("unknown", "unavailable", ""):
            return default
        return float(s)
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Core brain + persistence."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        self.runtime_settings: dict[str, float] = {
            SETTING_SOC_MIN: entry.options.get(SETTING_SOC_MIN, DEFAULT_SOC_MIN),
            SETTING_SOC_MAX: entry.options.get(SETTING_SOC_MAX, DEFAULT_SOC_MAX),
            SETTING_MAX_CHARGE: entry.options.get(SETTING_MAX_CHARGE, DEFAULT_MAX_CHARGE),
            SETTING_MAX_DISCHARGE: entry.options.get(SETTING_MAX_DISCHARGE, DEFAULT_MAX_DISCHARGE),
            SETTING_EMERGENCY_CHARGE_W: entry.options.get(
                SETTING_EMERGENCY_CHARGE_W, DEFAULT_EMERGENCY_CHARGE_W
            ),
            SETTING_EMERGENCY_SOC: entry.options.get(
                SETTING_EMERGENCY_SOC, DEFAULT_EMERGENCY_SOC
            ),
            SETTING_VERY_EXPENSIVE_THRESHOLD: entry.options.get(
                SETTING_VERY_EXPENSIVE_THRESHOLD, DEFAULT_VERY_EXPENSIVE_THRESHOLD
            ),
            SETTING_PROFIT_MARGIN_PCT: entry.options.get(
                SETTING_PROFIT_MARGIN_PCT, DEFAULT_PROFIT_MARGIN_PCT
            ),
        }

        data = entry.data or {}

        self.entities = EntityIds(
            soc=data[CONF_SOC_ENTITY],
            pv=data[CONF_PV_ENTITY],
            price_export=data.get(CONF_PRICE_EXPORT_ENTITY),
            price_now=data.get(CONF_PRICE_NOW_ENTITY),
            grid_mode=data.get(CONF_GRID_MODE, GRID_MODE_SINGLE),
            grid_power=data.get(CONF_GRID_POWER_ENTITY),
            grid_import=data.get(CONF_GRID_IMPORT_ENTITY),
            grid_export=data.get(CONF_GRID_EXPORT_ENTITY),
            ac_mode=data[CONF_AC_MODE_ENTITY],
            input_limit=data[CONF_INPUT_LIMIT_ENTITY],
            output_limit=data[CONF_OUTPUT_LIMIT_ENTITY],
        )

        self.runtime_mode: dict[str, str] = {
            "ai_mode": AI_MODE_AUTOMATIC,
            "manual_action": MANUAL_STANDBY,
        }

        self._store = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._persist: dict[str, Any] = {
            "runtime_mode": dict(self.runtime_mode),
            "emergency_active": False,
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

    async def async_shutdown(self) -> None:
        await self._save()

    async def _load(self) -> None:
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self._persist.update(stored)
            rm = self._persist.get("runtime_mode")
            if isinstance(rm, dict):
                self.runtime_mode.update({k: str(v) for k, v in rm.items()})

    async def _save(self) -> None:
        self._persist["runtime_mode"] = dict(self.runtime_mode)
        await self._store.async_save(self._persist)

    def _state(self, entity_id: str | None) -> Any:
        st = self.hass.states.get(entity_id) if entity_id else None
        return None if st is None else st.state

    def _attr(self, entity_id: str | None, attr: str) -> Any:
        st = self.hass.states.get(entity_id) if entity_id else None
        return None if st is None else st.attributes.get(attr)

    def _price_now(self) -> float | None:
        if self.entities.price_now:
            return _to_float(self._state(self.entities.price_now))
        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list):
            return None
        idx = int((dt_util.now().hour * 60 + dt_util.now().minute) // 15)
        try:
            return _to_float(export[idx].get("price_per_kwh"))
        except Exception:
            return None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            if self._persist["last_ts"] is None:
                await self._load()

            soc = _to_float(self._state(self.entities.soc))
            pv = _to_float(self._state(self.entities.pv))

            if soc is None or pv is None:
                return {
                    "status": STATUS_SENSOR_INVALID,
                    "ai_status": AI_STATUS_STANDBY,
                    "recommendation": RECO_STANDBY,
                    "debug": "SENSOR_INVALID",
                    "details": {},
                }

            soc_min = self._get_setting(SETTING_SOC_MIN, DEFAULT_SOC_MIN)
            emergency_soc = self._get_setting(SETTING_EMERGENCY_SOC, DEFAULT_EMERGENCY_SOC)
            emergency_w = self._get_setting(SETTING_EMERGENCY_CHARGE_W, DEFAULT_EMERGENCY_CHARGE_W)
            max_charge = self._get_setting(SETTING_MAX_CHARGE, DEFAULT_MAX_CHARGE)

            # -------- Emergency trigger --------
            if soc <= emergency_soc:
                self._persist["emergency_active"] = True

            ai_status = AI_STATUS_STANDBY
            recommendation = RECO_STANDBY
            ac_mode = ZENDURE_MODE_INPUT
            in_w = 0.0
            out_w = 0.0

            if self._persist.get("emergency_active"):
                ai_status = AI_STATUS_EMERGENCY_CHARGE
                recommendation = RECO_EMERGENCY
                in_w = min(max_charge, emergency_w)

                if soc >= soc_min:
                    self._persist["emergency_active"] = False

            await self._save()

            return {
                "status": STATUS_OK,
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "soc": soc,
                    "emergency_active": self._persist["emergency_active"],
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
