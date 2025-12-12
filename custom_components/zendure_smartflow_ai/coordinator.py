from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import now


class SmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Zentraler Daten- & Berechnungs-Coordinator"""

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry

        super().__init__(
            hass,
            logger=None,
            name="Zendure SmartFlow AI Coordinator",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self._collect_and_calculate()
        except Exception as err:
            raise UpdateFailed(f"SmartFlow Update fehlgeschlagen: {err}") from err

    async def _collect_and_calculate(self) -> dict[str, Any]:
        # ---------- ENTITÄTEN AUS CONFIG FLOW ----------
        soc_entity = self.entry.data["soc_entity"]
        price_entity = self.entry.data["price_export_entity"]
        cheap_threshold = self.entry.data["cheap_threshold"]
        expensive_threshold = self.entry.data["expensive_threshold"]
        max_charge = self.entry.data["max_charge"]
        max_discharge = self.entry.data["max_discharge"]
        battery_kwh = self.entry.data["battery_kwh"]
        soc_min = self.entry.data["soc_min"]
        soc_max = self.entry.data["soc_max"]

        # ---------- SOC ----------
        soc = float(self.hass.states.get(soc_entity).state)

        soc_clamped = max(0.0, min(100.0, soc))
        usable_kwh = battery_kwh * max(soc_clamped - soc_min, 0) / 100

        # ---------- PREISE ----------
        price_state = self.hass.states.get(price_entity)
        if not price_state:
            raise UpdateFailed("Preisquelle nicht verfügbar")

        export = price_state.attributes.get("data")
        if not export:
            raise UpdateFailed("Preisquelle enthält keine Daten")

        prices = [float(p["price_per_kwh"]) for p in export]

        if not prices:
            raise UpdateFailed("Preisliste leer")

        # Index ab JETZT (15-Minuten Raster)
        minutes_now = now().hour * 60 + now().minute
        idx_now = minutes_now // 15

        future_prices = prices[idx_now:]

        # ---------- PREISSTATISTIK ----------
        min_price = min(future_prices)
        max_price = max(future_prices)
        avg_price = sum(future_prices) / len(future_prices)
        span = max_price - min_price

        dynamic_expensive = avg_price + span * 0.25
        expensive = max(expensive_threshold, dynamic_expensive)

        # ---------- PEAKS ----------
        peak_slots = [p for p in future_prices if p >= expensive]
        peak_hours = len(peak_slots) * 0.25

        needed_kwh = peak_hours * (max_discharge / 1000)

        # ---------- ZUSAMMENBAU ----------
        return {
            "soc": soc_clamped,
            "soc_min": soc_min,
            "soc_max": soc_max,
            "usable_kwh": usable_kwh,
            "battery_kwh": battery_kwh,
            "prices": future_prices,
            "min_price": min_price,
            "max_price": max_price,
            "avg_price": avg_price,
            "expensive": expensive,
            "cheap": cheap_threshold,
            "needed_kwh": needed_kwh,
        }
