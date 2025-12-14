from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


# ==========================================================
# Basisklasse für alle Zendure-Number-Entitäten
# ==========================================================
class _BaseZendureNumber(NumberEntity):
    """Gemeinsame Basis für alle Number-Entities."""

    _attr_has_entity_name = True
    _attr_entity_category = None          # <- WICHTIG: sichtbar im Geräte-UI
    _attr_enabled_by_default = True        # <- sofort aktiv

    def __init__(
        self,
        coordinator: ZendureSmartFlowCoordinator,
        entry: ConfigEntry,
    ) -> None:
        self.coordinator = coordinator
        self.entry = entry
        self._attr_device_info = coordinator.device_info
        super().__init__()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


# ==========================================================
# SoC Minimum
# ==========================================================
class ZendureSocMinNumber(_BaseZendureNumber):
    _attr_translation_key = "soc_min"
    _attr_icon = "mdi:battery-alert"
    _attr_native_min_value = 5.0
    _attr_native_max_value = 40.0
    _attr_native_step = 1.0
    _attr_unit_of_measurement = "%"

    def __init__(
        self,
        coordinator: ZendureSmartFlowCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_soc_min"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("soc_min")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_soc_min(value)


# ==========================================================
# SoC Maximum
# ==========================================================
class ZendureSocMaxNumber(_BaseZendureNumber):
    _attr_translation_key = "soc_max"
    _attr_icon = "mdi:battery-charging-high"
    _attr_native_min_value = 50.0
    _attr_native_max_value = 100.0
    _attr_native_step = 1.0
    _attr_unit_of_measurement = "%"

    def __init__(
        self,
        coordinator: ZendureSmartFlowCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_soc_max"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("soc_max")

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_soc_max(value)


# ==========================================================
# Setup-Funktion
# ==========================================================
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
        ],
        update_before_add=True,
    )
