from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DATA_COORDINATOR


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [
            ZendureAiStatusSensor(coordinator, entry),
            ZendureRecommendationSensor(coordinator, entry),
            ZendureAiDebugSensor(coordinator, entry),
        ],
        True,
    )


class _BaseZendureSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "TK-Multimedia / Community",
            "model": "SmartFlow AI",
        }


class ZendureAiStatusSensor(_BaseZendureSensor):
    _attr_name = "Zendure SmartFlow AI Status"
    _attr_icon = "mdi:brain"

    @property
    def native_value(self) -> str:
        return str((self.coordinator.data or {}).get("ai_status", "init"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("details", {})


class ZendureRecommendationSensor(_BaseZendureSensor):
    _attr_name = "Zendure SmartFlow AI Steuerungsempfehlung"
    _attr_icon = "mdi:lightbulb-on-outline"

    @property
    def native_value(self) -> str:
        return str((self.coordinator.data or {}).get("recommendation", "init"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("details", {})


class ZendureAiDebugSensor(_BaseZendureSensor):
    _attr_name = "Zendure SmartFlow AI Debug"
    _attr_icon = "mdi:bug-outline"

    @property
    def native_value(self) -> str:
        dbg = (self.coordinator.data or {}).get("debug", "INIT")
        return str(dbg)[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("details", {})
