# custom_components/zendure_smartflow_ai/number.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_EXPENSIVE_THRESHOLD,
    SETTING_VERY_EXPENSIVE_THRESHOLD,
    SETTING_SURPLUS_THRESHOLD,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_EXPENSIVE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_SURPLUS_THRESHOLD,
)

STORAGE_VERSION = 1


@dataclass(frozen=True, kw_only=True)
class ZNumberDescription(NumberEntityDescription):
    setting_key: str
    default: float


NUMBERS: list[ZNumberDescription] = [
    ZNumberDescription(
        key=SETTING_SOC_MIN,
        setting_key=SETTING_SOC_MIN,
        default=float(DEFAULT_SOC_MIN),
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        translation_key="soc_min",
        icon="mdi:battery-low",
        unit_of_measurement="%",
    ),
    ZNumberDescription(
        key=SETTING_SOC_MAX,
        setting_key=SETTING_SOC_MAX,
        default=float(DEFAULT_SOC_MAX),
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        translation_key="soc_max",
        icon="mdi:battery-high",
        unit_of_measurement="%",
    ),
    ZNumberDescription(
        key=SETTING_MAX_CHARGE,
        setting_key=SETTING_MAX_CHARGE,
        default=float(DEFAULT_MAX_CHARGE),
        native_min_value=0,
        native_max_value=5000,
        native_step=1,
        translation_key="max_charge",
        icon="mdi:flash",
        unit_of_measurement="W",
    ),
    ZNumberDescription(
        key=SETTING_MAX_DISCHARGE,
        setting_key=SETTING_MAX_DISCHARGE,
        default=float(DEFAULT_MAX_DISCHARGE),
        native_min_value=0,
        native_max_value=5000,
        native_step=1,
        translation_key="max_discharge",
        icon="mdi:flash-outline",
        unit_of_measurement="W",
    ),
    ZNumberDescription(
        key=SETTING_EXPENSIVE_THRESHOLD,
        setting_key=SETTING_EXPENSIVE_THRESHOLD,
        default=float(DEFAULT_EXPENSIVE_THRESHOLD),
        native_min_value=0,
        native_max_value=2,
        native_step=0.01,
        translation_key="expensive_threshold",
        icon="mdi:cash-alert",
        unit_of_measurement="€/kWh",
    ),
    ZNumberDescription(
        key=SETTING_VERY_EXPENSIVE_THRESHOLD,
        setting_key=SETTING_VERY_EXPENSIVE_THRESHOLD,
        default=float(DEFAULT_VERY_EXPENSIVE_THRESHOLD),
        native_min_value=0,
        native_max_value=2,
        native_step=0.01,
        translation_key="very_expensive_threshold",
        icon="mdi:cash-lock",
        unit_of_measurement="€/kWh",
    ),
    ZNumberDescription(
        key=SETTING_SURPLUS_THRESHOLD,
        setting_key=SETTING_SURPLUS_THRESHOLD,
        default=float(DEFAULT_SURPLUS_THRESHOLD),
        native_min_value=0,
        native_max_value=2000,
        native_step=1,
        translation_key="surplus_threshold",
        icon="mdi:solar-power",
        unit_of_measurement="W",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.settings")

    data: dict[str, Any] = await store.async_load() or {}
    entities: list[ZendureSettingNumber] = []
    for desc in NUMBERS:
        entities.append(ZendureSettingNumber(entry, desc, store, data))
    async_add_entities(entities)


class ZendureSettingNumber(NumberEntity):
    def __init__(self, entry: ConfigEntry, desc: ZNumberDescription, store: Store, stored: dict[str, Any]):
        self.entity_description = desc
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_has_entity_name = True

        self._store = store
        self._stored = stored
        self._value = float(stored.get(desc.setting_key, desc.default))

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="Community",
            model="SmartFlow AI",
        )

    @property
    def native_value(self) -> float:
        return float(self._value)

    async def async_set_native_value(self, value: float) -> None:
        # keep clean numbers for most; thresholds allow decimals via native_step
        self._value = float(value)
        self._stored[self.entity_description.setting_key] = self._value
        await self._store.async_save(self._stored)
        self.async_write_ha_state()
