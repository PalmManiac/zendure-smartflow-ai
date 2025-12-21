from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, AI_MODES, MODE_AUTOMATIC
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureAIModeSelect(coordinator, entry)])


class ZendureAIModeSelect(SelectEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = "Moduswahl"
    _attr_icon = "mdi:toggle-switch-variant"
    _attr_options = AI_MODES

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_ai_mode"
        self._current = MODE_AUTOMATIC

    @property
    def device_info(self) -> dict[str, Any]:
        return self._coordinator.device_info

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        last = await self.async_get_last_state()
        if last and last.state in AI_MODES:
            self._current = last.state
        else:
            self._current = MODE_AUTOMATIC

        self._coordinator.settings.ai_mode = self._current
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        return self._current

    async def async_select_option(self, option: str) -> None:
        if option not in AI_MODES:
            return
        self._current = option
        self._coordinator.settings.ai_mode = option
        self.async_write_ha_state()
