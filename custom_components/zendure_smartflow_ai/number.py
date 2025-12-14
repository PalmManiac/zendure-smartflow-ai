from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .constants import DOMAIN, DEFAULT_SOC_MIN, DEFAULT_SOC_MAX
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ZendureSocMinNumber(coordinator, entry),
            ZendureSocMaxNumber(coordinator, entry),
        ]
    )


class _BaseZendureNumber(NumberEntity):
    _attr_native_min_value = 0.0
    _attr_native_max_value = 100.0
    _attr_native_step = 0.5
    _attr_unit_of_measurement = "%"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self.entry = entry

    async def _persist(self, key: str, value: float) -> None:
        await self.coordinator.async_set_setting(key, value)


class ZendureSocMinNumber(_BaseZendureNumber):
    _attr_icon = "mdi:battery-low"
    _attr_name = "Zendure SoC Minimum"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_internal_soc_min"

    @property
    def native_value(self) -> float:
        return float(self.coordinator.soc_min or DEFAULT_SOC_MIN)

    async def async_set_native_value(self, value: float) -> None:
        value = float(value)
        if self.coordinator.soc_max is not None and value >= self.coordinator.soc_max:
            value = max(0.0, self.coordinator.soc_max - 0.5)
        await self._persist("soc_min", value)


class ZendureSocMaxNumber(_BaseZendureNumber):
    _attr_icon = "mdi:battery-high"
    _attr_name = "Zendure SoC Maximum"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_internal_soc_max"

    @property
    def native_value(self) -> float:
        return float(self.coordinator.soc_max or DEFAULT_SOC_MAX)

    async def async_set_native_value(self, value: float) -> None:
        value = float(value)
        if self.coordinator.soc_min is not None and value <= self.coordinator.soc_min:
            value = min(100.0, self.coordinator.soc_min + 0.5)
        await self._persist("soc_max", value)
