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
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_AC_MODE_ENTITY,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = 10
FREEZE_SECONDS = 120

# ======================================================
# Betriebsmodi (Integration)
# ======================================================
MODE_AUTOMATIC = "automatic"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_MANUAL = "manual"


# ======================================================
# Entity Container
# ======================================================
@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str
    price_export: str
    ac_mode: str
    input_limit: str
    output_limit: str
    operation_mode: str


# ======================================================
# Helper
# ======================================================
def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return default


def _bad(value: Any) -> bool:
    return value in (None, "unknown", "unavailable", "")


# ======================================================
# Coordinator
# ======================================================
class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        data = entry.data

        # 🔑 WICHTIG: Entitäten aus Config Flow!
        self.entities = EntityIds(
            soc=data[CONF_SOC_ENTITY],
            pv=data[CONF_PV_ENTITY],
            load=data[CONF_LOAD_ENTITY],
            price_export=data.get(CONF_PRICE_NOW_ENTITY, ""),
            ac_mode=data[CONF_AC_MODE_ENTITY],
            input_limit="number.solarflow_2400_ac_input_limit",
            output_limit="number.solarflow_2400_ac_output_limit",
            operation_mode="select.zendure_betriebsmodus",
        )

        self._freeze_until: datetime | None = None
        self._last_ai_status: str | None = None
        self._last_recommendation: str | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # --------------------------------------------------
    # State helpers
    # --------------------------------------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # --------------------------------------------------
    # Preis jetzt (15-Minuten-Slot)
    # --------------------------------------------------
    def _price_now(self) -> float | None:
        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list):
            return None

        idx = int((dt_util.now().hour * 60 + dt_util.now().minute) // 15)
        try:
            return _to_float(export[idx].get("price_per_kwh"))
        except Exception:
            return None

    # --------------------------------------------------
    # Hardware erlauben?
    # --------------------------------------------------
    def _hardware_allowed(self, mode: str) -> bool:
        return mode != MODE_MANUAL

    # --------------------------------------------------
    # Hardware anwenden
    # --------------------------------------------------
    async def _apply_hardware(self, ac_mode: str, in_w: float, out_w: float) -> None:
        if not self._hardware_allowed(ac_mode):
            return

        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": ac_mode},
            blocking=False,
        )

        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": round(in_w, 0)},
            blocking=False,
        )

        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": round(out_w, 0)},
            blocking=False,
        )

    # ==================================================
    # Main Update
    # ==================================================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc_raw = self._state(self.entities.soc)
            pv_raw = self._state(self.entities.pv)
            load_raw = self._state(self.entities.load)

            if _bad(soc_raw) or _bad(load_raw):
                return {
                    "ai_status": "sensor_invalid",
                    "recommendation": "standby",
                    "debug": "SENSOR_INVALID",
                }

            soc = _to_float(soc_raw)
            pv = _to_float(pv_raw)
            load = _to_float(load_raw)

            price_now = self._price_now()

            surplus = max(pv - load, 0)

            ai_status = "standby"
            recommendation = "standby"
            ac_mode = "input"
            in_w = 0.0
            out_w = 0.0

            if surplus > 80:
                ai_status = "pv_laden"
                recommendation = "laden"
                in_w = surplus

            await self._apply_hardware(ac_mode, in_w, out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "soc": soc,
                    "pv": pv,
                    "load": load,
                    "surplus": surplus,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
