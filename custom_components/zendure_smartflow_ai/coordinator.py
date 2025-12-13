from __future__ import annotations

import logging
from datetime import timedelta
from typing import Dict, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=15),
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Zentrale KI-Auswertung"""

        try:
            return self._calculate()
        except Exception as err:
            _LOGGER.exception("SmartFlow AI error")
            return {
                "ai_status": "no_data",
                "recommendation": "error",
                "debug": f"Fehler: {err}",
            }

    # ---------------------------------------------------------------------

    def _calculate(self) -> Dict[str, Any]:
        """Portierte KI-Logik (V0.1 – direkt aus Jinja abgeleitet)"""

        # -------------------------
        # Basiswerte
        # -------------------------
        soc = self._f("sensor.solarflow_2400_ac_electric_level")
        soc_min = self._f("input_number.zendure_soc_reserve_min", 12)
        soc_max = self._f("input_number.zendure_soc_ziel_max", 95)

        battery_kwh = 5.76
        usable_kwh = max((soc - soc_min), 0) / 100 * battery_kwh

        # -------------------------
        # Preise (Tibber Datenexport)
        # -------------------------
        export = self.hass.states.get(
            "sensor.paul_schneider_strasse_39_diagramm_datenexport"
        )

        if not export or not export.attributes.get("data"):
            return self._result(
                ai_status="no_data",
                recommendation="error",
                debug="Keine Preisdaten verfügbar",
            )

        prices = [float(p["price_per_kwh"]) for p in export.attributes["data"]]
        if not prices:
            return self._result(
                ai_status="no_data",
                recommendation="error",
                debug="Preisliste leer",
            )

        current_price = prices[0]

        # -------------------------
        # Schwellen
        # -------------------------
        fixed_expensive = self._f("input_number.zendure_schwelle_teuer", 0.35)
        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        span = max_price - min_price

        expensive = max(fixed_expensive, avg_price + span * 0.25)

        # -------------------------
        # Peaks erkennen
        # -------------------------
        peak_indices = [i for i, p in enumerate(prices) if p >= expensive]

        if not peak_indices:
            return self._result(
                ai_status="no_peaks",
                recommendation="standby",
                debug="Keine relevanten Peaks erkannt",
            )

        peak_start_idx = peak_indices[0]
        minutes_to_peak = peak_start_idx * 15

        # -------------------------
        # günstigste Phase
        # -------------------------
        cheapest_idx = prices.index(min_price)
        cheapest_future = cheapest_idx > 0

        # -------------------------
        # Energiebedarf für Peaks
        # -------------------------
        discharge_w = self._f("input_number.zendure_max_entladeleistung", 700)
        peak_hours = len(peak_indices) * 0.25
        needed_kwh = peak_hours * (discharge_w / 1000)
        missing_kwh = max(needed_kwh - usable_kwh, 0)

        # -------------------------
        # Entscheidungslogik
        # -------------------------

        # 1) Peak läuft jetzt
        if current_price >= expensive:
            if soc <= soc_min:
                return self._result(
                    ai_status="peak_now",
                    recommendation="protect_battery",
                    debug="Teurer Preis, Akku unter Reserve",
                )
            else:
                return self._result(
                    ai_status="peak_now",
                    recommendation="discharge",
                    debug="Teurer Preis, Entladen empfohlen",
                )

        # 2) günstigste Phase kommt noch
        if cheapest_future and soc < soc_max:
            return self._result(
                ai_status="waiting_cheapest",
                recommendation="standby",
                debug="Günstigste Phase kommt noch",
            )

        # 3) günstigste Phase verpasst
        if not cheapest_future and soc < soc_max:
            return self._result(
                ai_status="missed_cheapest",
                recommendation="charge_grid",
                debug="Günstigste Phase wurde verpasst",
            )

        # 4) Peak später, Energie fehlt
        if missing_kwh > 0 and minutes_to_peak <= 180:
            return self._result(
                ai_status="peak_future",
                recommendation="charge_grid",
                debug="Laden notwendig für Peak",
            )

        # Fallback
        return self._result(
            ai_status="no_peaks",
            recommendation="standby",
            debug="Kein Handlungsbedarf",
        )

    # ---------------------------------------------------------------------

    def _f(self, entity_id: str, default: float = 0) -> float:
        state = self.hass.states.get(entity_id)
        try:
            return float(state.state)
        except Exception:
            return default

    def _result(self, ai_status: str, recommendation: str, debug: str) -> Dict[str, Any]:
        return {
            "ai_status": ai_status,
            "recommendation": recommendation,
            "debug": debug,
        }
