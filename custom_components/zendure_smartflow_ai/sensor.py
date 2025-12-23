from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_NAME, DEVICE_MANUFACTURER, DEVICE_MODEL
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = entry.runtime_data["coordinator"]
    async_add_entities(
        [
            ZendureAIStatusSensor(coordinator, entry),
            ZendureRecommendationSensor(coordinator, entry),
            ZendureDebugSensor(coordinator, entry),
        ]
    )


class _Base(CoordinatorEntity[ZendureSmartFlowCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": DEVICE_NAME,
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
        }


class ZendureAIStatusSensor(_Base):
    _attr_name = "AI Status"
    _attr_icon = "mdi:brain"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_ai_status"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("ai_status", "init")


class ZendureRecommendationSensor(_Base):
    _attr_name = "Steuerungsempfehlung"
    _attr_icon = "mdi:lightbulb"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_recommendation"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("recommendation", "init")


class ZendureDebugSensor(_Base):
    _attr_name = "AI Debug"
    _attr_icon = "mdi:bug"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_debug"

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("debug", "init")

    @property
    def extra_state_attributes(self):
        return (self.coordinator.data or {}).get("details", {})
