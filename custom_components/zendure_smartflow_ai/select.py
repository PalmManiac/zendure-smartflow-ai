from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


# ==================================================
# Betriebsmodi (intern)
# ==================================================
MODE_AUTOMATIC = "automatic"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_MANUAL = "manual"

MODES = [
    MODE_AUTOMATIC,
    MODE_SUMMER,
    MODE_WINTER,
    MODE_MANUAL,
]


# ==================================================
# Select Entity
# ==================================================
class ZendureOperationMode(SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Zendure Betriebsmodus"
    _attr_icon = "mdi:brain"
    _attr_options = MODES
    _attr_current_option = MODE_AUTOMATIC

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_operation_mode"

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


# ==================================================
# Setup
# ==================================================
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    async_add_entities([ZendureOperationMode(entry)])
