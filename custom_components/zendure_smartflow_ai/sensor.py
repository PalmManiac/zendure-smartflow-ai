from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
):
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ZendureSmartFlowStatusSensor(coordinator),
            ZendureSmartFlowRecommendationSensor(coordinator),
            ZendureSmartFlowDebugSensor(coordinator),
        ]
    )


# ============================================================
# 🔮 KI-STATUS SENSOR
# ============================================================

class ZendureSmartFlowStatusSensor(
    CoordinatorEntity,
    SensorEntity,
):
    _attr_name = "Zendure SmartFlow AI Status"
    _attr_icon = "mdi:brain"
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureSmartFlowCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_ai_status"

    @property
    def native_value(self):
        return self.coordinator.data.get("ai_status", "unknown")



# ============================================================
# ⚙️ STEUERUNGSEMPFEHLUNG
# ============================================================

class ZendureSmartFlowRecommendationSensor(
    CoordinatorEntity,
    SensorEntity,
):
    _attr_name = "Zendure Akku Steuerungsempfehlung"
    _attr_icon = "mdi:robot"
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureSmartFlowCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_recommendation"

    @property
    def native_value(self) -> str:
        return self.coordinator.data["recommendation"]


# ============================================================
# 🧪 DEBUG SENSOR (TEXT)
# ============================================================

class ZendureSmartFlowDebugSensor(
    CoordinatorEntity,
    SensorEntity,
):
    _attr_name = "Zendure SmartFlow AI Debug"
    _attr_icon = "mdi:bug"
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureSmartFlowCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_debug"

    @property
    def native_value(self) -> str:
        return self.coordinator.data["debug"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.coordinator.data.get("debug_attributes", {})
