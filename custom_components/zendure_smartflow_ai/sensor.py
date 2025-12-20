from homeassistant.components.sensor import SensorEntity

class ZendureStatusSensor(SensorEntity):
    _attr_name = "SmartFlow AI Status"

    def __init__(self, coordinator):
        self.coordinator = coordinator

    @property
    def native_value(self):
        return self.coordinator.data.get("ai_status")
