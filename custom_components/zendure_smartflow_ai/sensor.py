from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .constants import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ZendureSmartFlowStatusSensor(coordinator, entry),
            ZendureSmartFlowRecommendationSensor(coordinator, entry),
            ZendureSmartFlowDebugSensor(coordinator, entry),
        ],
        update_before_add=True,
    )


class _BaseZendureSensor(CoordinatorEntity[ZendureSmartFlowCoordinator], SensorEntity):
    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="PalmManiac",
            model="SF2400AC Controller",
        )


class ZendureSmartFlowStatusSensor(_BaseZendureSensor):
    _attr_name = "Zendure SmartFlow AI Status"
    _attr_icon = "mdi:robot"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_ai_status"

    @property
    def native_value(self) -> str:
        return str((self.coordinator.data or {}).get("ai_status", "standby"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "recommendation": data.get("recommendation"),
            "mode": data.get("mode"),
            "soc_min": data.get("soc_min"),
            "soc_max": data.get("soc_max"),
        }


class ZendureSmartFlowRecommendationSensor(_BaseZendureSensor):
    _attr_name = "Zendure Akku Steuerungsempfehlung"
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_recommendation"

    @property
    def native_value(self) -> str:
        return str((self.coordinator.data or {}).get("recommendation", "standby"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        details = data.get("details") or {}
        return {
            "ai_status": data.get("ai_status"),
            "mode": data.get("mode"),
            "price_now": data.get("price_now"),
            "expensive_threshold": data.get("expensive_threshold"),
            "details": details,
        }


class ZendureSmartFlowDebugSensor(_BaseZendureSensor):
    _attr_name = "Zendure SmartFlow AI Debug"
    _attr_icon = "mdi:bug-outline"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_debug"

    @property
    def native_value(self) -> str:
        dbg = (self.coordinator.data or {}).get("debug", "")
        if dbg is None:
            return ""
        return str(dbg)[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "ai_status": data.get("ai_status"),
            "recommendation": data.get("recommendation"),
            "mode": data.get("mode"),
            "price_now": data.get("price_now"),
            "expensive_threshold": data.get("expensive_threshold"),
            "details": data.get("details", {}),
        }
