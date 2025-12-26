from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    INTEGRATION_NAME,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_VERSION,
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD,
    SETTING_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
)

@dataclass(frozen=True, kw_only=True)
class ZendureNumberEntityDescription(NumberEntityDescription):
    setting_key: str


NUMBERS: tuple[ZendureNumberEntityDescription, ...] = (
    ZendureNumberEntityDescription(
        key="soc_min",
        translation_key="soc_min",
        setting_key=SETTING_SOC_MIN,
        icon="mdi:battery-10",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
    ),
    ZendureNumberEntityDescription(
        key="soc_max",
        translation_key="soc_max",
        setting_key=SETTING_SOC_MAX,
        icon="mdi:battery-90",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
    ),
    ZendureNumberEntityDescription(
        key="max_charge",
        translation_key="max_charge",
        setting_key=SETTING_MAX_CHARGE,
        icon="mdi:flash",
        native_min_value=0,
        native_max_value=2400,
        native_step=10,
        native_unit_of_measurement="W",
    ),
    ZendureNumberEntityDescription(
        key="max_discharge",
        translation_key="max_discharge",
        setting_key=SETTING_MAX_DISCHARGE,
        icon="mdi:flash-outline",
        native_min_value=0,
        native_max_value=2400,
        native_step=10,
        native_unit_of_measurement="W",
    ),
    ZendureNumberEntityDescription(
        key="price_threshold",
        translation_key="price_threshold",
        setting_key=SETTING_PRICE_THRESHOLD,
        icon="mdi:currency-eur",
        native_min_value=0,
        native_max_value=2.0,
        native_step=0.01,
        native_unit_of_measurement="€/kWh",
    ),
    ZendureNumberEntityDescription(
        key="very_expensive_threshold",
        translation_key="very_expensive_threshold",
        setting_key=SETTING_VERY_EXPENSIVE_THRESHOLD,
        icon="mdi:alert",
        native_min_value=0,
        native_max_value=2.0,
        native_step=0.01,
        native_unit_of_measurement="€/kWh",
    ),
)


DEFAULTS = {
    SETTING_SOC_MIN: DEFAULT_SOC_MIN,
    SETTING_SOC_MAX: DEFAULT_SOC_MAX,
    SETTING_MAX_CHARGE: DEFAULT_MAX_CHARGE,
    SETTING_MAX_DISCHARGE: DEFAULT_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD: DEFAULT_PRICE_THRESHOLD,
    SETTING_VERY_EXPENSIVE_THRESHOLD: DEFAULT_VERY_EXPENSIVE_THRESHOLD,
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    # Init defaults once (so coordinator has values)
    for k, v in DEFAULTS.items():
        coordinator.settings.setdefault(k, float(v))

    add_entities([ZendureSmartFlowNumber(entry, coordinator, d) for d in NUMBERS])


class ZendureSmartFlowNumber(NumberEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator, description: ZendureNumberEntityDescription) -> None:
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

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> float | None:
        return float(self.coordinator.settings.get(self.entity_description.setting_key, 0.0))

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.settings[self.entity_description.setting_key] = float(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
