from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
)

# ---- kleine Helfer -----------------------------------------------------------

def _to_float(v: Any, default: float) -> float:
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return default


@dataclass(frozen=True, kw_only=True)
class ZendureNumberEntityDescription(NumberEntityDescription):
    setting_key: str
    default: float
    min_value: float
    max_value: float
    step: float


DESCRIPTIONS: tuple[ZendureNumberEntityDescription, ...] = (
    ZendureNumberEntityDescription(
        key="soc_min",
        translation_key="soc_min",
        name="SoC Minimum",
        setting_key=SETTING_SOC_MIN,
        default=float(DEFAULT_SOC_MIN),
        min_value=5.0,
        max_value=95.0,
        step=1.0,
        icon="mdi:battery-10",
        entity_category=EntityCategory.CONFIG,
    ),
    ZendureNumberEntityDescription(
        key="soc_max",
        translation_key="soc_max",
        name="SoC Maximum",
        setting_key=SETTING_SOC_MAX,
        default=float(DEFAULT_SOC_MAX),
        min_value=10.0,
        max_value=100.0,
        step=1.0,
        icon="mdi:battery",
        entity_category=EntityCategory.CONFIG,
    ),
    ZendureNumberEntityDescription(
        key="max_charge",
        translation_key="max_charge",
        name="Max. Ladeleistung",
        setting_key=SETTING_MAX_CHARGE,
        default=float(DEFAULT_MAX_CHARGE),
        min_value=0.0,
        max_value=3000.0,
        step=10.0,
        icon="mdi:flash",
        entity_category=EntityCategory.CONFIG,
    ),
    ZendureNumberEntityDescription(
        key="max_discharge",
        translation_key="max_discharge",
        name="Max. Entladeleistung",
        setting_key=SETTING_MAX_DISCHARGE,
        default=float(DEFAULT_MAX_DISCHARGE),
        min_value=0.0,
        max_value=3000.0,
        step=10.0,
        icon="mdi:flash-outline",
        entity_category=EntityCategory.CONFIG,
    ),
    ZendureNumberEntityDescription(
        key="price_threshold",
        translation_key="price_threshold",
        name="Teuer-Schwelle",
        setting_key=SETTING_PRICE_THRESHOLD,
        default=float(DEFAULT_PRICE_THRESHOLD),
        min_value=0.05,
        max_value=1.50,
        step=0.001,  # Anzeige runden wir später in 0.6.1/0.7 – technisch besser so
        icon="mdi:currency-eur",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    store = hass.data[DOMAIN][entry.entry_id].setdefault("settings", {})

    entities: list[ZendureSettingNumber] = []
    for desc in DESCRIPTIONS:
        entities.append(ZendureSettingNumber(coordinator, entry, store, desc))

    async_add_entities(entities)


class ZendureBaseEntity(CoordinatorEntity):
    """Sorgt für saubere Gerätezuordnung + stabile unique_ids."""
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="PalmManiac / Community",
            model="SmartFlow AI",
            entry_type=DeviceEntryType.SERVICE,
        )


class ZendureSettingNumber(ZendureBaseEntity, NumberEntity):
    entity_description: ZendureNumberEntityDescription

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        store: dict[str, float],
        description: ZendureNumberEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._store = store

        # unique_id: absolut eindeutig pro Entry + pro Setting
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        # Wertebereich
        self._attr_native_min_value = description.min_value
        self._attr_native_max_value = description.max_value
        self._attr_native_step = description.step
        self._attr_native_unit_of_measurement = description.unit_of_measurement

        # Default setzen, wenn noch nicht vorhanden
        if description.setting_key not in self._store:
            self._store[description.setting_key] = float(description.default)

    @property
    def native_value(self) -> float:
        return float(self._store.get(self.entity_description.setting_key, self.entity_description.default))

    async def async_set_native_value(self, value: float) -> None:
        # speichern – coordinator liest es beim nächsten Update aus hass.data
        self._store[self.entity_description.setting_key] = float(value)
        self.async_write_ha_state()
