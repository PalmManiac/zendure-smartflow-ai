from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
)
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True)
class _NumDesc:
    key: str
    name: str
    icon: str
    min_value: float
    max_value: float
    step: float
    unit: str | None


NUMBERS = [
    _NumDesc("soc_min", "SoC Minimum", "mdi:battery-low", 0.0, 100.0, 1.0, "%"),
    _NumDesc("soc_max", "SoC Maximum", "mdi:battery-high", 0.0, 100.0, 1.0, "%"),
    _NumDesc("max_charge", "Max Ladeleistung", "mdi:flash", 0.0, 6000.0, 50.0, "W"),
    _NumDesc("max_discharge", "Max Entladeleistung", "mdi:flash-outline", 0.0, 6000.0, 50.0, "W"),
    _NumDesc("price_threshold", "Teuer-Schwelle", "mdi:currency-eur", 0.0, 2.0, 0.001, "€/kWh"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureSettingNumber(coordinator, entry, d) for d in NUMBERS])


class ZendureSettingNumber(NumberEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_mode = "box"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry, desc: _NumDesc) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._desc = desc

        self._attr_unique_id = f"{entry.entry_id}_setting_{desc.key}"
        self._attr_name = desc.name
        self._attr_icon = desc.icon
        self._attr_native_min_value = desc.min_value
        self._attr_native_max_value = desc.max_value
        self._attr_native_step = desc.step
        self._attr_native_unit_of_measurement = desc.unit

        self._value: float | None = None

    @property
    def device_info(self) -> dict[str, Any]:
        return self._coordinator.device_info

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Restore
        last = await self.async_get_last_state()
        if last and last.state not in ("unknown", "unavailable", ""):
            try:
                self._value = float(str(last.state).replace(",", "."))
            except Exception:
                self._value = None

        # Default, falls nix restored
        if self._value is None:
            defaults = {
                "soc_min": DEFAULT_SOC_MIN,
                "soc_max": DEFAULT_SOC_MAX,
                "max_charge": DEFAULT_MAX_CHARGE,
                "max_discharge": DEFAULT_MAX_DISCHARGE,
                "price_threshold": DEFAULT_PRICE_THRESHOLD,
            }
            self._value = float(defaults[self._desc.key])

        # in Coordinator Settings übernehmen
        setattr(self._coordinator.settings, self._desc.key, float(self._value))

        # sofort einmal refreshen
        self._coordinator.async_set_updated_data(self._coordinator.data or {})

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        self._value = float(value)
        setattr(self._coordinator.settings, self._desc.key, float(self._value))
        self.async_write_ha_state()
