# custom_components/zendure_smartflow_ai/sensor.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True, kw_only=True)
class ZSensorDescription(SensorEntityDescription):
    key: str


SENSORS: list[ZSensorDescription] = [
    ZSensorDescription(
        key="ai_status",
        translation_key="ai_status",
        icon="mdi:robot",
    ),
    ZSensorDescription(
        key="recommendation",
        translation_key="recommendation",
        icon="mdi:lightbulb-outline",
    ),
    ZSensorDescription(
        key="debug",
        translation_key="debug",
        icon="mdi:bug-outline",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureSmartFlowSensor(coordinator, entry, d) for d in SENSORS])


class ZendureSmartFlowSensor(SensorEntity):
    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry, desc: ZSensorDescription):
        self.coordinator = coordinator
        self.entity_description = desc
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_has_entity_name = True

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="Community",
            model="SmartFlow AI",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        return data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        details = data.get("details", {})
        if self.entity_description.key == "debug":
            # show key debug info
            return {"details": details}
        if self.entity_description.key in ("ai_status", "recommendation"):
            return details if isinstance(details, dict) else {}
        return {}
