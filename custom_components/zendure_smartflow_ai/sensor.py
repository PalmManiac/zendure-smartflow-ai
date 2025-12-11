from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN, DEFAULT_NAME

async def async_setup_entry(hass, entry, async_add_entities):
    # Hier werden später die KI-Sensoren erstellt
    async_add_entities([ZendureStatusSensor()])

class ZendureStatusSensor(SensorEntity):
    _attr_name = f"{DEFAULT_NAME} Status"

    @property
    def state(self):
        return "init"
