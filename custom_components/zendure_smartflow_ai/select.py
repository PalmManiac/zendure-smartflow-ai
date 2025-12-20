from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    AI_MODES,
    DEFAULT_AI_MODE,
    AI_MODE_AUTOMATIC,
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    async_add_entities([ZendureAIModeSelect(entry)])


class ZendureAIModeSelect(SelectEntity):
    """AI Betriebsmodus (nicht Hardware!)"""

    _attr_has_entity_name = True
    _attr_translation_key = "ai_mode"
    _attr_icon = "mdi:robot"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_ai_mode"
        self._attr_options = AI_MODES
        self._attr_current_option = DEFAULT_AI_MODE

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="Community",
            model="SmartFlow AI",
        )

    async def async_select_option(self, option: str) -> None:
        if option not in AI_MODES:
            return

        self._attr_current_option = option
        self.async_write_ha_state()

        # 🔗 an Coordinator durchreichen
        coordinator = self.hass.data[DOMAIN][self._entry.entry_id]
        coordinator.set_ai_mode(option)
