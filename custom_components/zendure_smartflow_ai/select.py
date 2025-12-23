# custom_components/zendure_smartflow_ai/select.py
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    AI_MODES,
    MANUAL_ACTIONS,
    MODE_AUTOMATIC,
    MANUAL_STANDBY,
)
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ZendureAiModeSelect(coordinator, entry),
            ZendureManualActionSelect(coordinator, entry),
        ]
    )


class _BaseSelect(SelectEntity):
    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry):
        self.coordinator = coordinator
        self.entry = entry

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Zendure SmartFlow AI",
            manufacturer="Community",
            model="SmartFlow AI",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class ZendureAiModeSelect(_BaseSelect):
    _attr_has_entity_name = True
    _attr_translation_key = "ai_mode"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_ai_mode"
        self._attr_options = AI_MODES
        self._attr_current_option = MODE_AUTOMATIC

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        await self.coordinator.async_set_operation_mode(option)
        self.async_write_ha_state()


class ZendureManualActionSelect(_BaseSelect):
    _attr_has_entity_name = True
    _attr_translation_key = "manual_action"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_manual_action"
        self._attr_options = MANUAL_ACTIONS
        self._attr_current_option = MANUAL_STANDBY

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        await self.coordinator.async_set_manual_action(option)
        self.async_write_ha_state()
