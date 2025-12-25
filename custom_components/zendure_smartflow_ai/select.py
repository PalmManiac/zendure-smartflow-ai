from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_ACTION_STANDBY,
    MANUAL_ACTION_CHARGE,
    MANUAL_ACTION_DISCHARGE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            ZendureAiModeSelect(entry),
            ZendureManualActionSelect(entry),
        ],
        True,
    )


class _BaseSelect(SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, unique: str, name: str):
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{unique}"
        self._attr_name = name

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "Zendure",
            "model": "SmartFlow AI",
        }


class ZendureAiModeSelect(_BaseSelect):
    def __init__(self, entry: ConfigEntry):
        super().__init__(entry, "ai_mode", "AI Modus")
        self.entity_id = f"select.{DOMAIN}_ai_mode"
        self._attr_options = [
            AI_MODE_AUTOMATIC,
            AI_MODE_SUMMER,
            AI_MODE_WINTER,
            AI_MODE_MANUAL,
        ]
        self._current = AI_MODE_AUTOMATIC

    @property
    def current_option(self) -> str:
        return self._current

    async def async_select_option(self, option: str) -> None:
        self._current = option
        self.async_write_ha_state()


class ZendureManualActionSelect(_BaseSelect):
    def __init__(self, entry: ConfigEntry):
        super().__init__(entry, "manual_action", "Manuelle Aktion")
        self.entity_id = f"select.{DOMAIN}_manual_action"
        self._attr_options = [
            MANUAL_ACTION_STANDBY,
            MANUAL_ACTION_CHARGE,
            MANUAL_ACTION_DISCHARGE,
        ]
        self._current = MANUAL_ACTION_STANDBY

    @property
    def current_option(self) -> str:
        return self._current

    async def async_select_option(self, option: str) -> None:
        self._current = option
        self.async_write_ha_state()
