from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ZendureSocMin(coordinator, entry),
            ZendureSocMax(coordinator, entry),
        ]
    )


class _BaseZendureNumber(NumberEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self.entry = entry


class ZendureSocMin(_BaseZendureNumber):
    _attr_name = "Zendure SoC Minimum"
    _attr_icon = "mdi:battery-alert"
    _attr_native_min_value = 5
    _attr_native_max_value = 50
    _attr_native_step = 1

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_soc_min"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("soc_min")

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.data["soc_min"] = round(value, 0)
        self.async_write_ha_state()


class ZendureSocMax(_BaseZendureNumber):
    _attr_name = "Zendure SoC Maximum"
    _attr_icon = "mdi:battery-high"
    _attr_native_min_value = 50
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_soc_max"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("soc_max")

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.data["soc_max"] = round(value, 0)
        self.async_write_ha_state()
