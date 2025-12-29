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
    INTEGRATION_NAME,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_VERSION,
)


@dataclass(frozen=True, kw_only=True)
class ZendureNumberEntityDescription(NumberEntityDescription):
    runtime_key: str


NUMBERS: tuple[ZendureNumberEntityDescription, ...] = (
    ZendureNumberEntityDescription(
        key="soc_min",
        translation_key="soc_min",
        runtime_key="soc_min",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        icon="mdi:battery-alert",
    ),
    ZendureNumberEntityDescription(
        key="soc_max",
        translation_key="soc_max",
        runtime_key="soc_max",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        icon="mdi:battery-check",
    ),
    ZendureNumberEntityDescription(
        key="max_charge",
        translation_key="max_charge",
        runtime_key="max_charge",
        native_min_value=0,
        native_max_value=2400,
        native_step=50,
        native_unit_of_measurement="W",
        icon="mdi:battery-arrow-up",
    ),
    ZendureNumberEntityDescription(
        key="max_discharge",
        translation_key="max_discharge",
        runtime_key="max_discharge",
        native_min_value=0,
        native_max_value=2400,
        native_step=50,
        native_unit_of_measurement="W",
        icon="mdi:battery-arrow-down",
    ),
    ZendureNumberEntityDescription(
        key="emergency_charge",
        translation_key="emergency_charge",
        runtime_key="emergency_charge",
        native_min_value=0,
        native_max_value=2400,
        native_step=50,
        native_unit_of_measurement="W",
        icon="mdi:flash-alert",
    ),
    ZendureNumberEntityDescription(
        key="emergency_soc",
        translation_key="emergency_soc",
        runtime_key="emergency_soc",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        icon="mdi:alert-circle",
    ),
    ZendureNumberEntityDescription(
        key="profit_margin_pct",
        translation_key="profit_margin_pct",
        runtime_key="profit_margin_pct",
        min_value=0,
        max_value=1000,
        step=1,
        unit_of_measurement="%",
        icon="mdi:chart-line",
    ),
    ZendureNumberEntityDescription(
        key="very_expensive_threshold",
        translation_key="very_expensive_threshold",
        runtime_key="very_expensive_threshold",
        native_min_value=0,
        native_max_value=2,
        native_step=0.01,
        native_unit_of_measurement="€/kWh",
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

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        description: ZendureNumberEntityDescription,
    ) -> None:
        self.entity_description = description
        self.coordinator = coordinator
        self._entry = entry

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": INTEGRATION_NAME,
            "manufacturer": INTEGRATION_MANUFACTURER,
            "model": INTEGRATION_MODEL,
            "sw_version": INTEGRATION_VERSION,
        }

        if description.runtime_key not in coordinator.runtime_settings:
            coordinator.runtime_settings[description.runtime_key] = entry.options.get(
                description.runtime_key,
                description.native_min_value,
            )

    @property
    def native_value(self) -> float:
        return float(self.coordinator.runtime_settings.get(self.entity_description.runtime_key, 0))

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.runtime_settings[self.entity_description.runtime_key] = value

        await self.hass.config_entries.async_update_entry(
            self._entry,
            options={
                **self._entry.options,
                self.entity_description.runtime_key: value,
            },
        )

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
