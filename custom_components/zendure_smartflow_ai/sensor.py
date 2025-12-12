from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_STATUS, SENSOR_RECOMMENDATION


async def async_setup_entry(
    hass: HomeAssistant,
    entry,
    async_add_entities: AddEntitiesCallback,
):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            SmartFlowStatusSensor(coordinator),
            SmartFlowRecommendationSensor(coordinator),
        ]
    )


class SmartFlowBaseSensor(CoordinatorEntity, SensorEntity):
    """Basisklasse für alle SmartFlow Sensoren"""

    _attr_has_entity_name = True

    def __init__(self, coordinator, sensor_type: str):
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{sensor_type}"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class SmartFlowStatusSensor(SmartFlowBaseSensor):
    """KI-Ladeplan Status"""

    _attr_name = "SmartFlow KI-Status"
    _attr_icon = "mdi:brain"

    def __init__(self, coordinator):
        super().__init__(coordinator, SENSOR_STATUS)

    @property
    def native_value(self):
        data = self.coordinator.data

        if not data or "prices" not in data:
            return "datenproblem_preisquelle"

        prices = data["prices"]
        soc = data["soc"]
        soc_min = data["soc_min"]
        soc_max = data["soc_max"]

        current_price = prices[0]

        expensive = data["expensive"]

        # Peak-Erkennung
        peaks = [p for p in prices if p >= expensive]

        if not peaks:
            return "keine_peaks_heute"

        # Peak läuft gerade
        if current_price >= expensive:
            if soc <= soc_min:
                return "teuer_jetzt_akkuschutz"
            return "teuer_jetzt_entladen_empfohlen"

        # günstigster Preis in Zukunft?
        min_price = min(prices)
        cheapest_idx = prices.index(min_price)

        if cheapest_idx > 0 and soc < soc_max:
            return "günstige_phase_kommt_noch"

        if cheapest_idx == 0 and soc < soc_max:
            return "günstigste_phase_verpasst"

        # Energiebedarf grob
        usable_kwh = data["usable_kwh"]
        needed_kwh = data["needed_kwh"]

        if needed_kwh > usable_kwh:
            return "laden_notwendig_für_peak"

        return "keine_ladung_notwendig"


class SmartFlowRecommendationSensor(SmartFlowBaseSensor):
    """Konkrete Steuerungsempfehlung"""

    _attr_name = "SmartFlow Steuerungsempfehlung"
    _attr_icon = "mdi:battery-heart"

    def __init__(self, coordinator):
        super().__init__(coordinator, SENSOR_RECOMMENDATION)

    @property
    def native_value(self):
        status = self.coordinator.data.get("status")

        if status in (
            "laden_notwendig_für_peak",
            "günstigste_phase_verpasst",
        ):
            return "ki_laden"

        if status == "teuer_jetzt_entladen_empfohlen":
            return "entladen"

        if status == "teuer_jetzt_akkuschutz":
            return "standby"

        if status == "günstige_phase_kommt_noch":
            return "warten"

        return "standby"
