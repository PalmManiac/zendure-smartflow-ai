from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coord = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ZendureStatusSensor(coord),
        ZendureRecommendationSensor(coord),
        ZendureDebugSensor(coord),
    ])


class _Base(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True


class ZendureStatusSensor(_Base):
    _attr_name = "Status"
    _attr_translation_key = "ai_status"

    @property
    def native_value(self):
        return self.coordinator.data.get("ai_status")


class ZendureRecommendationSensor(_Base):
    _attr_name = "Steuerungsempfehlung"
    _attr_translation_key = "recommendation"

    @property
    def native_value(self):
        return self.coordinator.data.get("recommendation")


class ZendureDebugSensor(_Base):
    _attr_name = "Debug"
    _attr_translation_key = "debug"

    @property
    def native_value(self):
        return self.coordinator.data.get("debug")
