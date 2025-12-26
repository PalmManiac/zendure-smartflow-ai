from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import *

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityIds:
    soc: str
    pv: str

    grid_power: str | None
    grid_import: str | None
    grid_export: str | None

    price_export: str | None

    ac_mode: str
    input_limit: str
    output_limit: str


def _to_float(val: Any, default: float | None = None) -> float | None:
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        data = entry.data

        self.entities = EntityIds(
            soc=data[CONF_SOC_ENTITY],
            pv=data[CONF_PV_ENTITY],
            grid_power=data.get(CONF_GRID_POWER_ENTITY),
            grid_import=data.get(CONF_GRID_IMPORT_ENTITY),
            grid_export=data.get(CONF_GRID_EXPORT_ENTITY),
            price_export=data.get(CONF_PRICE_EXPORT_ENTITY),
            ac_mode=data[CONF_AC_MODE_ENTITY],
            input_limit=data[CONF_INPUT_LIMIT_ENTITY],
            output_limit=data[CONF_OUTPUT_LIMIT_ENTITY],
        )

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # --------------------------------------------------
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

    # --------------------------------------------------
    def _price_now(self) -> float | None:
        if not self.entities.price_export:
            return None

        data = self._attr(self.entities.price_export, "data")
        if not isinstance(data, list):
            return None

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        if idx >= len(data):
            return None

        return _to_float(data[idx].get("price_per_kwh"))

    # --------------------------------------------------
    def _grid_power(self) -> float:
        if self.entities.grid_power:
            return _to_float(self._state(self.entities.grid_power), 0.0) or 0.0

        imp = _to_float(self._state(self.entities.grid_import), 0.0) or 0.0
        exp = _to_float(self._state(self.entities.grid_export), 0.0) or 0.0
        return imp - exp

    # --------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc = _to_float(self._state(self.entities.soc), 0.0) or 0.0
            pv = _to_float(self._state(self.entities.pv), 0.0) or 0.0

            grid_power = self._grid_power()
            house_load = pv + grid_power

            price_now = self._price_now()

            ai_status = "standby"
            recommendation = "standby"

            # ---------- KI-Logik ----------
            if price_now is not None:
                if price_now >= DEFAULT_PRICE_VERY_EXPENSIVE and soc > DEFAULT_SOC_MIN:
                    ai_status = "sehr_teuer"
                    recommendation = "entladen"

                elif price_now >= DEFAULT_PRICE_EXPENSIVE and soc > DEFAULT_SOC_MIN:
                    ai_status = "teuer"
                    recommendation = "entladen"

            surplus = max(pv - house_load, 0.0)

            if surplus > 100 and soc < DEFAULT_SOC_MAX:
                ai_status = "pv_ueberschuss"
                recommendation = "laden"

            # ---------- Hardware-Steuerung ----------
            if recommendation == "laden":
                await self.hass.services.async_call(
                    "select",
                    "select_option",
                    {
                        "entity_id": self.entities.ac_mode,
                        "option": "input",
                    },
                    blocking=False,
                )
                await self.hass.services.async_call(
                    "number",
                    "set_value",
                    {
                        "entity_id": self.entities.input_limit,
                        "value": min(DEFAULT_MAX_CHARGE, surplus),
                    },
                    blocking=False,
                )

            elif recommendation == "entladen":
                await self.hass.services.async_call(
                    "select",
                    "select_option",
                    {
                        "entity_id": self.entities.ac_mode,
                        "option": "output",
                    },
                    blocking=False,
                )
                await self.hass.services.async_call(
                    "number",
                    "set_value",
                    {
                        "entity_id": self.entities.output_limit,
                        "value": min(DEFAULT_MAX_DISCHARGE, house_load),
                    },
                    blocking=False,
                )

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "house_load": round(house_load, 1),
                "price_now": price_now,
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
