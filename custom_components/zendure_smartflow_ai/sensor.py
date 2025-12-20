from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up Zendure SmartFlow AI sensors."""
    async_add_entities(
        [
            ZendureSmartFlowStatusSensor(entry),
        ]
    )


class ZendureSmartFlowStatusSensor(Entity):
    """Minimaler Status-Sensor (Platzhalter)."""

    _attr_name = "Zendure SmartFlow AI Status"
    _attr_icon = "mdi:robot"

    def __init__(self, entry: ConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "Zendure",
            "model": "SolarFlow AI",
        }

    @property
    def state(self):
        return "online"
