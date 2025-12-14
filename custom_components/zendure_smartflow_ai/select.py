from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DEVICE_NAME,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ZendureSocMinNumber(coordinator, entry),
            ZendureSocMaxNumber(coordinator, entry),
        ]
    )


class _BaseSocNumber(NumberEntity):
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = "box"

    def __init__(self, coordinator, entry: ConfigEntry):
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
            "name": DEVICE_NAME,
        }


class ZendureSocMinNumber(_BaseSocNumber):
    _attr_name = "Zendure SoC Minimum"
    _attr_icon = "mdi:battery-low"

    def __init__(self, coordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_soc_min"
        self._attr_native_value = DEFAULT_SOC_MIN

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()


class ZendureSocMaxNumber(_BaseSocNumber):
    _attr_name = "Zendure SoC Maximum"
    _attr_icon = "mdi:battery-high"

    def __init__(self, coordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_soc_max"
        self._attr_native_value = DEFAULT_SOC_MAX

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
