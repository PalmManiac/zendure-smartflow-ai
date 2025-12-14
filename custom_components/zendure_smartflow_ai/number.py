from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .constants import (
    DOMAIN,
    DEFAULT_SOC_MAX,
    DEFAULT_SOC_MIN,
    OPT_SOC_MAX,
    OPT_SOC_MIN,
)
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ZendureSocMinNumber(coordinator, entry),
            ZendureSocMaxNumber(coordinator, entry),
        ],
        update_before_add=True,
    )


class _BaseNumber(CoordinatorEntity[ZendureSmartFlowCoordinator], NumberEntity):
    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="PalmManiac",
            model="SF2400AC Controller",
        )


class ZendureSocMinNumber(_BaseNumber):
    _attr_name = "Zendure SoC Minimum"
    _attr_icon = "mdi:battery-low"
    _attr_native_unit_of_measurement = "%"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 50.0
    _attr_native_step = 1.0

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_soc_min"

    @property
    def native_value(self) -> float:
        return float(self.coordinator.get_option_float(OPT_SOC_MIN, DEFAULT_SOC_MIN))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.set_option(OPT_SOC_MIN, float(value))


class ZendureSocMaxNumber(_BaseNumber):
    _attr_name = "Zendure SoC Maximum"
    _attr_icon = "mdi:battery-high"
    _attr_native_unit_of_measurement = "%"
    _attr_native_min_value = 50.0
    _attr_native_max_value = 100.0
    _attr_native_step = 1.0

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_soc_max"

    @property
    def native_value(self) -> float:
        return float(self.coordinator.get_option_float(OPT_SOC_MAX, DEFAULT_SOC_MAX))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.set_option(OPT_SOC_MAX, float(value))
