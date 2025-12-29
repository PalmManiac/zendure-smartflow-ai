from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_NAME,
    INTEGRATION_VERSION,
)


@dataclass(frozen=True, kw_only=True)
class ZendureNumberEntityDescription(NumberEntityDescription):
    runtime_key: str
    min_value: float
    max_value: float
    step: float


# ==================================================
# UI-Reihenfolge (so wie von dir gewünscht)
# ==================================================
NUMBERS: tuple[ZendureNumberEntityDescription, ...] = (
    # SoC Minimum
    ZendureNumberEntityDescription(
        key="soc_min",
        translation_key="soc_min",
        runtime_key="soc_min",
        min_value=0,
        max_value=100,
        step=1,
        unit_of_measurement="%",
        icon="mdi:battery-alert",
    ),

    # SoC Maximum
    ZendureNumberEntityDescription(
        key="soc_max",
        translation_key="soc_max",
        runtime_key="soc_max",
        min_value=0,
        max_value=100,
        step=1,
        unit_of_measurement="%",
        icon="mdi:battery-check",
    ),

    # Max. Ladeleistung
    ZendureNumberEntityDescription(
        key="max_charge",
        translation_key="max_charge_power",
        runtime_key="max_charge",
        min_value=0,
        max_value=2400,
        step=50,
        unit_of_measurement="W",
        icon="mdi:battery-arrow-up",
    ),

    # Max. Entladeleistung
    ZendureNumberEntityDescription(
        key="max_discharge",
        translation_key="max_discharge_power",
        runtime_key="max_discharge",
        min_value=0,
        max_value=2400,
        step=50,
        unit_of_measurement="W",
        icon="mdi:battery-arrow-down",
    ),

    # Notladeleistung
    ZendureNumberEntityDescription(
        key="emergency_charge_w",
        translation_key="emergency_charge_power",
        runtime_key="emergency_charge_w",
        min_value=0,
        max_value=2400,
        step=50,
        unit_of_measurement="W",
        icon="mdi:flash-alert",
    ),

    # Notladung ab SoC
    ZendureNumberEntityDescription(
        key="emergency_soc",
        translation_key="emergency_soc",
        runtime_key="emergency_soc",
        min_value=0,
        max_value=100,
        step=1,
        unit_of_measurement="%",
        icon="mdi:alert-circle",
    ),

    # Sehr teuer Schwelle
    ZendureNumberEntityDescription(
        key="very_expensive_threshold",
        translation_key="very_expensive_threshold",
        runtime_key="very_expensive_threshold",
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

        # Initialwert sicherstellen
        if description.runtime_key not in coordinator.runtime_settings:
            coordinator.runtime_settings[description.runtime_key] = description.min_value

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> float:
        return self.coordinator.runtime_settings.get(
            self.entity_description.runtime_key,
            self.entity_description.min_value,
        )

    async def async_set_native_value(self, value: float) -> None:
        # Runtime setzen
        self.coordinator.runtime_settings[self.entity_description.runtime_key] = value

        # Persistenz
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
