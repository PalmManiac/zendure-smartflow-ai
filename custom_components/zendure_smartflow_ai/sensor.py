from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True)
class _SensorDesc:
    key: str
    name: str
    icon: str


SENSORS = [
    _SensorDesc("ai_status", "AI Status", "mdi:robot"),
    _SensorDesc("recommendation", "Steuerungsempfehlung", "mdi:lightbulb-auto"),
    _SensorDesc("debug", "AI Debug", "mdi:bug-outline"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [ZendureAISensor(coordinator, entry, d) for d in SENSORS]
    async_add_entities(entities)


class ZendureAISensor(CoordinatorEntity[ZendureSmartFlowCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry, desc: _SensorDesc) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._desc = desc
        self._attr_unique_id = f"{entry.entry_id}_sensor_{desc.key}"
        self._attr_name = desc.name
        self._attr_icon = desc.icon

    @property
    def device_info(self) -> dict[str, Any]:
        return self.coordinator.device_info

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        return data.get(self._desc.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        details = data.get("details") or {}
        if not isinstance(details, dict):
            details = {}
        return details
