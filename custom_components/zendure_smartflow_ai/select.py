from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    DATA_COORDINATOR,
    SETTING_OPERATION_MODE,
    SETTING_MANUAL_ACTION,
    DEFAULT_OPERATION_MODE,
    DEFAULT_MANUAL_ACTION,
    MODE_AUTOMATIC,
    MODE_SUMMER,
    MODE_WINTER,
    MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [
            ZendureOperationModeSelect(hass, entry, coordinator),
            ZendureManualActionSelect(hass, entry, coordinator),
        ],
        True,
    )


class _BaseSelect(SelectEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "TK-Multimedia / Community",
            "model": "SmartFlow AI",
        }


class ZendureOperationModeSelect(_BaseSelect):
    _attr_name = "Zendure SmartFlow AI Moduswahl"
    _attr_icon = "mdi:cog-outline"
    _attr_options = [MODE_AUTOMATIC, MODE_SUMMER, MODE_WINTER, MODE_MANUAL]

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_operation_mode"

    @property
    def current_option(self) -> str:
        return (self.entry.options or {}).get(SETTING_OPERATION_MODE, DEFAULT_OPERATION_MODE)

    async def async_select_option(self, option: str) -> None:
        opts = dict(self.entry.options or {})
        opts[SETTING_OPERATION_MODE] = option
        self.hass.config_entries.async_update_entry(self.entry, options=opts)
        await self.coordinator.async_request_refresh()


class ZendureManualActionSelect(_BaseSelect):
    _attr_name = "Zendure SmartFlow AI Manuell Aktion"
    _attr_icon = "mdi:hand-back-left-outline"
    _attr_options = [MANUAL_STANDBY, MANUAL_CHARGE, MANUAL_DISCHARGE]

    @property
    def unique_id(self) -> str:
        return f"{self.entry.entry_id}_manual_action"

    @property
    def current_option(self) -> str:
        return (self.entry.options or {}).get(SETTING_MANUAL_ACTION, DEFAULT_MANUAL_ACTION)

    async def async_select_option(self, option: str) -> None:
        opts = dict(self.entry.options or {})
        opts[SETTING_MANUAL_ACTION] = option
        self.hass.config_entries.async_update_entry(self.entry, options=opts)
        await self.coordinator.async_request_refresh()
