from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_EXPENSIVE_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)

# ✅ FIX: war vorher undefiniert -> NameError
UPDATE_INTERVAL = 10  # Sekunden


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
        if val is None:
            return default
        s = str(val).replace(",", ".")
        if s.lower() in ("unknown", "unavailable", ""):
            return default
        return float(s)
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """V0.4.x – liest Sensoren/Preise und liefert Status/Empfehlung (und je nach Version ggf. Hardware-Steuerung)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        data = entry.data or {}

        # robust gegen fehlende Keys
        def pick(key: str, fallback: str = "") -> str:
            v = data.get(key)
            return v if isinstance(v, str) and v else fallback

        self.entities = EntityIds(
            soc=pick(CONF_SOC_ENTITY),
            pv=pick(CONF_PV_ENTITY),
            load=pick(CONF_LOAD_ENTITY),
            price_export=pick(CONF_PRICE_EXPORT_ENTITY),
            ac_mode=pick(CONF_AC_MODE_ENTITY),
            input_limit=pick(CONF_INPUT_LIMIT_ENTITY),
            output_limit=pick(CONF_OUTPUT_LIMIT_ENTITY),
        )

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # -----------------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    def _price_now(self) -> float | None:
        data = self._attr(self.entities.price_export, "data")
        if not isinstance(data, list) or not data:
            return None

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        if idx < 0 or idx >= len(data):
            return None

        item = data[idx]
        if not isinstance(item, dict):
            return None
        return _to_float(item.get("price_per_kwh"), default=None)

    # -----------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc = _to_float(self._state(self.entities.soc), 0.0) or 0.0
            pv = _to_float(self._state(self.entities.pv), 0.0) or 0.0
            load = _to_float(self._state(self.entities.load), 0.0) or 0.0

            price_now = self._price_now()

            # Basissachen für Debug/Details
            surplus = max(pv - load, 0.0)
            deficit = max(load - pv, 0.0)

            if price_now is None:
                return {
                    "ai_status": "price_invalid",
                    "recommendation": "standby",
                    "debug": "PRICE_INVALID",
                    "details": {
                        "soc": soc,
                        "pv": pv,
                        "load": load,
                        "surplus": surplus,
                        "deficit": deficit,
                        "price_export_entity": self.entities.price_export,
                    },
                }

            # (V0.4.x) nur Bewertung/Empfehlung (falls deine Hardwaresteuerung in anderer Version liegt)
            ai_status = "standby"
            recommendation = "standby"

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
                    "expensive_threshold": DEFAULT_EXPENSIVE_THRESHOLD,
                    "soc_min_default": DEFAULT_SOC_MIN,
                    "soc_max_default": DEFAULT_SOC_MAX,
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
