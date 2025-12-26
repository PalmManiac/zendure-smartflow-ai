from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_NAME,
    INTEGRATION_VERSION,
    AI_MODES,
    MANUAL_ACTIONS,
    AI_MODE_AUTOMATIC,
    MANUAL_STANDBY,
)


@dataclass(frozen=True, kw_only=True)
class ZendureSelectEntityDescription(SelectEntityDescription):
    runtime_key: str
    options_list: list[str]
    default_option: str


SELECTS: tuple[ZendureSelectEntityDescription, ...] = (
    ZendureSelectEntityDescription(
        key="ai_mode",
        translation_key="ai_mode",
        runtime_key="ai_mode",
        options_list=AI_MODES,
        default_option=AI_MODE_AUTOMATIC,
        icon="mdi:robot",
    ),
    ZendureSelectEntityDescription(
        key="manual_action",
        translation_key="manual_action",
        runtime_key="manual_action",
        options_list=MANUAL_ACTIONS,
        default_option=MANUAL_STANDBY,
        icon="mdi:gesture-tap-button",
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    add_entities([ZendureSmartFlowSelect(entry, coordinator, d) for d in SELECTS])


class ZendureSmartFlowSelect(SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator, description: ZendureSelectEntityDescription) -> None:
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

        self._attr_options = list(description.options_list)

        if description.runtime_key not in coordinator.runtime_mode:
            coordinator.runtime_mode[description.runtime_key] = description.default_option

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def current_option(self) -> str | None:
        return self.coordinator.runtime_mode.get(self.entity_description.runtime_key)

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            return
        self.coordinator.runtime_mode[self.entity_description.runtime_key] = option
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
