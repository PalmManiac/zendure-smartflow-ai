from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .constants import DOMAIN, MODES
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureModeSelect(coordinator, entry)])


class ZendureModeSelect(SelectEntity):
    _attr_name = "Zendure Betriebsmodus"
    _attr_icon = "mdi:robot"
    _attr_options = MODES
    _attr_translation_key = "mode"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry):
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_mode"

    @property
    def current_option(self) -> str:
        return self.coordinator.mode

    async def async_select_option(self, option: str) -> None:
        self.coordinator.mode = option
        await self.coordinator.async_request_refresh()
