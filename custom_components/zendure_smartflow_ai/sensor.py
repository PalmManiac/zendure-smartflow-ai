from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, INTEGRATION_MANUFACTURER, INTEGRATION_MODEL, INTEGRATION_NAME, INTEGRATION_VERSION


@dataclass(frozen=True, kw_only=True)
class ZendureSensorEntityDescription(SensorEntityDescription):
    key: str


SENSORS: tuple[ZendureSensorEntityDescription, ...] = (
    ZendureSensorEntityDescription(
        key="status",
        translation_key="status",
        icon="mdi:check-circle",
    ),
    ZendureSensorEntityDescription(
        key="ai_status",
        translation_key="ai_status",
        icon="mdi:robot",
    ),
    ZendureSensorEntityDescription(
        key="ai_debug",
        translation_key="ai_debug",
        icon="mdi:bug",
    ),
    ZendureSensorEntityDescription(
        key="load",
        translation_key="load",
        icon="mdi:home-lightning-bolt",
        native_unit_of_measurement="W",
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    add_entities([ZendureSmartFlowSensor(entry, coordinator, d) for d in SENSORS])


class ZendureSmartFlowSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator, description: ZendureSensorEntityDescription) -> None:
        self.entity_description = description
        self.coordinator = coordinator
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": INTEGRATION_NAME,
            "manufacturer": INTEGRATION_MANUFACTURER,
            "model": INTEGRATION_MODEL,
            "sw_version": INTEGRATION_VERSION,
        }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        key = self.entity_description.key
        if key == "load":
            details = data.get("details", {}) or {}
            return details.get("load")
        return data.get(key)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()
