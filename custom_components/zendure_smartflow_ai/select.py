from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import (
    DOMAIN,
    DEVICE_NAME,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    AI_MODES,
    AI_MODE_AUTO,
    MANUAL_ACTIONS,
    MANUAL_STANDBY,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    async_add_entities(
        [
            ZendureAIModeSelect(entry),
            ZendureManualActionSelect(entry),
        ]
    )


class _BaseSelect(SelectEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": DEVICE_NAME,
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
        }


class ZendureAIModeSelect(_BaseSelect):
    _attr_name = "Moduswahl"
    _attr_icon = "mdi:brain"
    _attr_options = AI_MODES

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_current_option = AI_MODE_AUTO
        self._attr_suggested_object_id = f"{DOMAIN}_mode"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_ai_mode"

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


class ZendureManualActionSelect(_BaseSelect):
    _attr_name = "Manuelle Aktion"
    _attr_icon = "mdi:gesture-tap"
    _attr_options = MANUAL_ACTIONS

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_current_option = MANUAL_STANDBY
        self._attr_suggested_object_id = f"{DOMAIN}_manual_action"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_manual_action"

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()
