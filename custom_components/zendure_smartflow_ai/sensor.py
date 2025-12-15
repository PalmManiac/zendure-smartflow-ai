from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import ZendureSmartFlowCoordinator
from .const import DOMAIN


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities):
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ZendureSmartFlowStatusSensor(coordinator, entry),
            ZendureRecommendationSensor(coordinator, entry),
            ZendureSmartFlowDebugSensor(coordinator, entry),
        ]
    )


class _BaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "Zendure",
            "model": "SmartFlow AI",
        }


class ZendureSmartFlowStatusSensor(_BaseSensor):
    _attr_name = "Zendure SmartFlow AI Status"
    _attr_icon = "mdi:brain"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_ai_status"

    @property
    def native_value(self):
        return self.coordinator.data.get("ai_status")


class ZendureRecommendationSensor(_BaseSensor):
    _attr_name = "Zendure Akku Steuerungsempfehlung"
    _attr_icon = "mdi:lightbulb-on-outline"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_recommendation"

    @property
    def native_value(self):
        return self.coordinator.data.get("recommendation")


class ZendureSmartFlowDebugSensor(_BaseSensor):
    _attr_name = "Zendure SmartFlow AI Debug"
    _attr_icon = "mdi:bug-outline"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_debug"

    @property
    def native_value(self):
        return self.coordinator.data.get("debug")

    @property
    def extra_state_attributes(self):
        return self.coordinator.data.get("details", {})
