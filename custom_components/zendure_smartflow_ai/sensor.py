from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    async_add_entities([
        SimpleSensor(entry, "AI Status"),
        SimpleSensor(entry, "Steuerungsempfehlung"),
        SimpleSensor(entry, "Debug"),
    ])


class SimpleSensor(SensorEntity):
    def __init__(self, entry, name):
        self._attr_unique_id = f"{entry.entry_id}_{name}"
        self._attr_name = f"Zendure SmartFlow {name}"
        self._attr_native_value = "init"

    def set(self, value):
        self._attr_native_value = value
        self.async_write_ha_state()
