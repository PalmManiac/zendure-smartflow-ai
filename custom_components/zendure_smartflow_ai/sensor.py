from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ZendureSmartFlowStatusSensor(coordinator),
            ZendureAkkuSteuerungsempfehlungSensor(coordinator),
            ZendureSmartFlowDebugSensor(coordinator),
        ]
    )


class ZendureBaseSensor(CoordinatorEntity, SensorEntity):
    """Basisklasse für alle Zendure SmartFlow Sensoren"""

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "Zendure",
            "model": "SF2400AC (SmartFlow AI)",
            "sw_version": "0.1.0",
        }


class ZendureSmartFlowStatusSensor(ZendureBaseSensor):
    _attr_name = "Zendure SmartFlow AI Status"
    _attr_icon = "mdi:brain"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_ai_status"

    @property
    def native_value(self):
        return self.coordinator.data.get("ai_status")

    @property
    def extra_state_attributes(self):
        return {
            "beschreibung": self.coordinator.data.get("ai_status_text"),
            "letzte_aktualisierung": self.coordinator.data.get("timestamp"),
        }


class ZendureAkkuSteuerungsempfehlungSensor(ZendureBaseSensor):
    _attr_name = "Zendure Akku Steuerungsempfehlung"
    _attr_icon = "mdi:battery-charging-outline"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_recommendation"

    @property
    def native_value(self):
        return self.coordinator.data.get("recommendation")

    @property
    def extra_state_attributes(self):
        return {
            "quelle": "Zendure SmartFlow AI",
            "begründung": self.coordinator.data.get("recommendation_reason"),
            "ai_status": self.coordinator.data.get("ai_status"),
        }


class ZendureSmartFlowDebugSensor(ZendureBaseSensor):
    _attr_name = "Zendure SmartFlow AI Debug"
    _attr_icon = "mdi:bug-outline"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_debug"

    @property
    def native_value(self):
        return self.coordinator.data.get("debug_short")

    @property
    def extra_state_attributes(self):
        return self.coordinator.data.get("debug", {})
