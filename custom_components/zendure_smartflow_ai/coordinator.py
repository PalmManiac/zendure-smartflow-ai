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

UPDATE_INTERVAL = 10

@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str
    price_export: str
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
            load=data[CONF_LOAD_ENTITY],
            price_export=data[CONF_PRICE_EXPORT_ENTITY],
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
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # --------------------------------------------------
    def _price_now(self) -> float | None:
        data = self._attr(self.entities.price_export, "data")
        if not isinstance(data, list):
            return None

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        if idx >= len(data):
            return None

        return _to_float(data[idx].get("price_per_kwh"))

    # --------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc = _to_float(self._state(self.entities.soc), 0.0)
            pv = _to_float(self._state(self.entities.pv), 0.0)
            load = _to_float(self._state(self.entities.load), 0.0)

            price_now = self._price_now()
            if price_now is None:
                return {
                    "ai_status": "price_invalid",
                    "recommendation": "standby",
                    "debug": "PRICE_INVALID",
                }

            surplus = max(pv - load, 0.0)
            deficit = max(load - pv, 0.0)

            ai_status = "standby"
            recommendation = "standby"

            # 👉 KEINE HARDWARE-STEUERUNG HIER
            # Diese Version bewertet NUR – Steuerung folgt v0.3.0

            if price_now >= DEFAULT_EXPENSIVE_THRESHOLD and soc > DEFAULT_SOC_MIN:
                ai_status = "teuer"
                recommendation = "entladen"

            elif surplus > 100 and soc < DEFAULT_SOC_MAX:
                ai_status = "pv_ueberschuss"
                recommendation = "laden"

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "soc": soc,
                    "pv": pv,
                    "load": load,
                    "price_now": price_now,
                    "surplus": surplus,
                    "deficit": deficit,
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
