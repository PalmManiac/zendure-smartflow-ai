from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN


OPTIONS = [
    "Automatik",
    "Sommer",
    "Winter",
    "Manuell",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureBetriebsmodus(coordinator, entry)])


class ZendureBetriebsmodus(SelectEntity):
    _attr_name = "Zendure Betriebsmodus"
    _attr_icon = "mdi:toggle-switch"
    _attr_options = OPTIONS
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_mode"

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.get("mode")

    async def async_select_option(self, option: str) -> None:
        # Modus nur setzen – Logik greift im Coordinator
        self.coordinator.data["mode"] = option
        self.async_write_ha_state()
