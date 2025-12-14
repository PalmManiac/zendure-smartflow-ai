from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ZendureSmartFlowStatusSensor(coordinator, entry),
            ZendureSmartFlowRecommendationSensor(coordinator, entry),
            ZendureSmartFlowDebugSensor(coordinator, entry),
        ]
    )


class _BaseZendureSensor(CoordinatorEntity[ZendureSmartFlowCoordinator], SensorEntity):
    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def should_poll(self) -> bool:
        return False


class ZendureSmartFlowStatusSensor(_BaseZendureSensor):
    _attr_name = "Zendure SmartFlow AI Status"
    _attr_icon = "mdi:robot"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_ai_status"

    @property
    def native_value(self) -> str:
        return (self.coordinator.data or {}).get("ai_status", "unbekannt")


class ZendureSmartFlowRecommendationSensor(_BaseZendureSensor):
    _attr_name = "Zendure Akku Steuerungsempfehlung"
    _attr_icon = "mdi:battery-sync"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_recommendation"

    @property
    def native_value(self) -> str:
        return (self.coordinator.data or {}).get("recommendation", "standby")


class ZendureSmartFlowDebugSensor(_BaseZendureSensor):
    _attr_name = "Zendure SmartFlow AI Debug"
    _attr_icon = "mdi:bug-outline"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_debug"

    @property
    def native_value(self) -> str:
        # State kurz halten (max 255)
        dbg = (self.coordinator.data or {}).get("debug", "OK")
        return str(dbg)[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "ai_status": data.get("ai_status"),
            "recommendation": data.get("recommendation"),
            "details": data.get("details", {}),
        }
