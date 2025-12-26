from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_EXPENSIVE_THRESHOLD,
)


@dataclass(frozen=True, kw_only=True)
class ZendureNumberEntityDescription(NumberEntityDescription):
    runtime_key: str
    default: float


NUMBERS: tuple[ZendureNumberEntityDescription, ...] = (
    ZendureNumberEntityDescription(
        key="soc_min",
        translation_key="soc_min",
        runtime_key="soc_min",
        default=DEFAULT_SOC_MIN,
        min_value=0,
        max_value=100,
        step=1,
        unit_of_measurement="%",
        icon="mdi:battery-low",
    ),
    ZendureNumberEntityDescription(
        key="soc_max",
        translation_key="soc_max",
        runtime_key="soc_max",
        default=DEFAULT_SOC_MAX,
        min_value=0,
        max_value=100,
        step=1,
        unit_of_measurement="%",
        icon="mdi:battery-high",
    ),
    ZendureNumberEntityDescription(
        key="max_charge",
        translation_key="max_charge",
        runtime_key="max_charge",
        default=DEFAULT_MAX_CHARGE,
        min_value=0,
        max_value=3000,
        step=50,
        unit_of_measurement="W",
        icon="mdi:battery-arrow-up",
    ),
    ZendureNumberEntityDescription(
        key="max_discharge",
        translation_key="max_discharge",
        runtime_key="max_discharge",
        default=DEFAULT_MAX_DISCHARGE,
        min_value=0,
        max_value=3000,
        step=50,
        unit_of_measurement="W",
        icon="mdi:battery-arrow-down",
    ),
    ZendureNumberEntityDescription(
        key="price_threshold",
        translation_key="price_threshold",
        runtime_key="price_threshold",
        default=DEFAULT_EXPENSIVE_THRESHOLD,
        min_value=0,
        max_value=2,
        step=0.01,
        unit_of_measurement="€/kWh",
        icon="mdi:currency-eur",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    add_entities(
        ZendureSmartFlowNumber(entry, coordinator, description)
        for description in NUMBERS
    )


class ZendureSmartFlowNumber(NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator, description: ZendureNumberEntityDescription) -> None:
        self.entity_description = description
        self.coordinator = coordinator

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

        if description.runtime_key not in coordinator.runtime_config:
            coordinator.runtime_config[description.runtime_key] = description.default

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> float:
        return self.coordinator.runtime_config[self.entity_description.runtime_key]

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.runtime_config[self.entity_description.runtime_key] = value
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
