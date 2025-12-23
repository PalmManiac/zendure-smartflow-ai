from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import *

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([ZendureAIModeSelect(entry)])


class ZendureAIModeSelect(SelectEntity):
    _attr_name = "Zendure SmartFlow AI Modus"
    _attr_icon = "mdi:robot"
    _attr_options = [
        "Automatik",
        "Sommer",
        "Winter",
        "Manuell",
    ]

    def __init__(self, entry: ConfigEntry):
        self._attr_unique_id = f"{entry.entry_id}_ai_mode"
        self._attr_current_option = "Automatik"

    @property
    def current_mode(self) -> str:
        return {
            "Automatik": AI_MODE_AUTO,
            "Sommer": AI_MODE_SUMMER,
            "Winter": AI_MODE_WINTER,
            "Manuell": AI_MODE_MANUAL,
        }[self._attr_current_option]

    async def async_select_option(self, option: str):
        self._attr_current_option = option
        self.async_write_ha_state()
