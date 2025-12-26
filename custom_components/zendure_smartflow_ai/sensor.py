from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_STATUS, SENSOR_AI_STATUS, SENSOR_AI_DEBUG
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True, kw_only=True)
class ZendureSensorEntityDescription(SensorEntityDescription):
    pass


SENSORS: tuple[ZendureSensorEntityDescription, ...] = (
    ZendureSensorEntityDescription(
        key=SENSOR_STATUS,
        translation_key="status",
        icon="mdi:check-network",
    ),
    ZendureSensorEntityDescription(
        key=SENSOR_AI_STATUS,
        translation_key="ai_status",
        icon="mdi:robot",
    ),
    ZendureSensorEntityDescription(
        key=SENSOR_AI_DEBUG,
        translation_key="ai_debug",
        icon="mdi:bug",
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ZendureAISensor(coordinator, entry, desc) for desc in SENSORS])


class ZendureAISensor(CoordinatorEntity[ZendureSmartFlowCoordinator], SensorEntity):
    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry, desc: ZendureSensorEntityDescription):
        super().__init__(coordinator)
        self.entity_description = desc
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "PalmManiac",
            "model": "SmartFlow AI",
        }

    @property
    def native_value(self):
        key = self.entity_description.key
        return (self.coordinator.data or {}).get(key)

    @property
    def extra_state_attributes(self):
        return (self.coordinator.data or {}).get("details", {})
