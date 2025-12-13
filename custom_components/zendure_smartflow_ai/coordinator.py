from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .ai_logic import calculate_ai_state

_LOGGER = logging.getLogger(__name__)


class ZendureSmartFlowCoordinator(DataUpdateCoordinator):
    """Zendure SmartFlow AI – zentraler Datenkoordinator"""

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        """Zentrale Datenaktualisierung"""

        # ---------- Helper ----------
        def get_float(entity_id, default=0.0):
            try:
                state = self.hass.states.get(entity_id)
                if state is None:
                    return default
                return float(state.state)
            except Exception:
                return default

        # ---------- Basiswerte ----------
        soc = get_float("sensor.solarflow_2400_ac_electric_level")
        soc_min = get_float("input_number.zendure_soc_reserve_min", 12)
        soc_max = get_float("input_number.zendure_soc_ziel_max", 95)

        max_charge = get_float("input_number.zendure_max_ladeleistung", 2000)
        max_discharge = get_float("input_number.zendure_max_entladeleistung", 700)
        expensive_threshold = get_float("input_number.zendure_schwelle_teuer", 0.35)

        battery_kwh = 5.76

        # ---------- Preisdaten ----------
        prices = []

        export = self.hass.states.get(
            "sensor.paul_schneider_strasse_39_diagramm_datenexport"
        )

        if export and export.attributes.get("data"):
            try:
                prices = [
                    float(p["price_per_kwh"])
                    for p in export.attributes["data"]
                ]
            except Exception as err:
                _LOGGER.warning("Preisimport fehlgeschlagen: %s", err)

        # ---------- KI berechnen ----------
        ai_result = calculate_ai_state(
            prices=prices,
            soc=soc,
            soc_min=soc_min,
            soc_max=soc_max,
            battery_kwh=battery_kwh,
            max_charge_w=max_charge,
            max_discharge_w=max_discharge,
            expensive_threshold=expensive_threshold,
        )

        # ---------- Ergebnis für Sensoren ----------
        return {
            "ai_status": ai_result.get("ai_status"),
            "ai_status_text": ai_result.get("ai_status_text"),
            "recommendation": ai_result.get("recommendation"),
            "recommendation_reason": ai_result.get("recommendation_reason"),
            "debug": ai_result.get("debug", {}),
            "debug_short": ai_result.get("debug_short", ""),
        }
