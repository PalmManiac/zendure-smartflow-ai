from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# -------------------------------------------------
# Interne Werte (dürfen NIE geändert werden!)
# -------------------------------------------------
MODE_AUTOMATIC = "automatic"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_MANUAL = "manual"

AI_MODES = [
    MODE_AUTOMATIC,
    MODE_SUMMER,
    MODE_WINTER,
    MODE_MANUAL,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([ZendureAIModeSelect(entry)])


class ZendureAIModeSelect(SelectEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "ai_mode"
    _attr_icon = "mdi:brain"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_ai_mode"
        self._attr_options = AI_MODES
        self._attr_current_option = MODE_AUTOMATIC

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "Zendure",
            "model": "SmartFlow AI",
        }

    async def async_select_option(self, option: str) -> None:
        if option not in AI_MODES:
            return

        self._attr_current_option = option
        self.async_write_ha_state()
