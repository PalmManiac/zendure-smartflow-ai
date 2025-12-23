from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import *

_LOGGER = logging.getLogger(__name__)


def _to_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self.data_cfg = entry.data

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    async def _set_select(self, entity_id: str, option: str):
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": option},
            blocking=False,
        )

    async def _set_number(self, entity_id: str, value: float):
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id, "value": int(round(value, 0))},
            blocking=False,
        )

    # --------------------------------------------------
    # Strompreis (Tibber Datenexport)
    # --------------------------------------------------
    def _price_now(self) -> float | None:
        data = self._attr(self.data_cfg[CONF_PRICE_EXPORT_ENTITY], "data")
        if not isinstance(data, list):
            return None

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        if idx >= len(data):
            return None

        return _to_float(data[idx].get("price_per_kwh"))

    # --------------------------------------------------
    # Main Update
    # --------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # ---------------------------
            # Rohwerte
            # ---------------------------
            soc = _to_float(self._state(self.data_cfg[CONF_SOC_ENTITY]))
            pv = _to_float(self._state(self.data_cfg[CONF_PV_ENTITY]))
            load = _to_float(self._state(self.data_cfg[CONF_LOAD_ENTITY]))

            price_now = self._price_now()
            if price_now is None:
                return {
                    "ai_status": "price_invalid",
                    "recommendation": "standby",
                    "debug": "PRICE_INVALID",
                }

            surplus = max(pv - load, 0.0)
            deficit = max(load - pv, 0.0)

            # ---------------------------
            # Einstellungen (Number)
            # ---------------------------
            soc_min = DEFAULT_SOC_MIN
            soc_max = DEFAULT_SOC_MAX
            max_charge = DEFAULT_MAX_CHARGE
            max_discharge = DEFAULT_MAX_DISCHARGE
            expensive = DEFAULT_EXPENSIVE
            very_expensive = DEFAULT_VERY_EXPENSIVE

            # ---------------------------
            # AI Mode
            # ---------------------------
            ai_mode_state = self.hass.states.get(
                f"select.{DOMAIN}_ai_mode"
            )
            ai_mode = AI_MODE_AUTO
            if ai_mode_state:
                ai_mode = {
                    "Automatik": AI_MODE_AUTO,
                    "Sommer": AI_MODE_SUMMER,
                    "Winter": AI_MODE_WINTER,
                    "Manuell": AI_MODE_MANUAL,
                }.get(ai_mode_state.state, AI_MODE_AUTO)

            # ---------------------------
            # MANUELL → KEINE KI
            # ---------------------------
            if ai_mode == AI_MODE_MANUAL:
                return {
                    "ai_status": "manual",
                    "recommendation": "manuell",
                    "debug": "MANUAL_MODE_ACTIVE",
                }

            # ---------------------------
            # Entscheidung
            # ---------------------------
            ai_status = "standby"
            recommendation = "standby"

            set_mode = None
            set_input = 0
            set_output = 0

            # === SEHR TEUER → IMMER ENTLADE ===
            if price_now >= very_expensive and soc > soc_min:
                ai_status = "sehr_teuer"
                recommendation = "entladen"
                set_mode = "output"
                set_output = min(max_discharge, deficit)

            # === TEUER (Winter / Auto) ===
            elif price_now >= expensive and soc > soc_min and ai_mode in (
                AI_MODE_AUTO,
                AI_MODE_WINTER,
            ):
                ai_status = "teuer"
                recommendation = "entladen"
                set_mode = "output"
                set_output = min(max_discharge, deficit)

            # === SOMMER / AUTO → PV ÜBERSCHUSS LADEN ===
            elif surplus > 100 and soc < soc_max and ai_mode in (
                AI_MODE_AUTO,
                AI_MODE_SUMMER,
            ):
                ai_status = "pv_ueberschuss"
                recommendation = "laden"
                set_mode = "input"
                set_input = min(max_charge, surplus)

            # ---------------------------
            # Hardware setzen
            # ---------------------------
            if set_mode:
                await self._set_select(self.data_cfg[CONF_AC_MODE_ENTITY], set_mode)
                await self._set_number(self.data_cfg[CONF_INPUT_LIMIT_ENTITY], set_input)
                await self._set_number(self.data_cfg[CONF_OUTPUT_LIMIT_ENTITY], set_output)

            # ---------------------------
            # Rückgabe
            # ---------------------------
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
                    "mode": ai_mode,
                    "set_mode": set_mode,
                    "set_input_w": set_input,
                    "set_output_w": set_output,
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
