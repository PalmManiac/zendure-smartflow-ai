from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    MODES,
    MODE_AUTO,
    MODE_SUMMER,
    MODE_WINTER,
    MODE_MANUAL,
    SETTING_MODE,
    DEFAULT_MODE,
)
from .coordinator import ZendureSmartFlowCoordinator


MODE_LABELS: dict[str, str] = {
    MODE_AUTO: "Automatik",
    MODE_SUMMER: "Sommer (Autarkie)",
    MODE_WINTER: "Winter (Preis)",
    MODE_MANUAL: "Manuell (AI aus)",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureModeSelect(coordinator, entry)])


class ZendureModeSelect(SelectEntity, RestoreEntity):
    _attr_name = "Zendure Betriebsmodus"
    _attr_icon = "mdi:toggle-switch"
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self.entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_mode"
        self._attr_options = [MODE_LABELS[m] for m in MODES]

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "PalmManiac",
            "model": "SmartFlow AI",
        }

    def _label_to_value(self, label: str) -> str:
        for k, v in MODE_LABELS.items():
            if v == label:
                return k
        return DEFAULT_MODE

    def _value_to_label(self, value: str) -> str:
        return MODE_LABELS.get(value, MODE_LABELS[DEFAULT_MODE])

    @property
    def current_option(self) -> str | None:
        v = str(self.coordinator.settings.get(SETTING_MODE, DEFAULT_MODE))
        return self._value_to_label(v)

    async def async_select_option(self, option: str) -> None:
        self.coordinator.settings[SETTING_MODE] = self._label_to_value(option)
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state:
            # restore label -> internal value
            self.coordinator.settings[SETTING_MODE] = self._label_to_value(last.state)
        else:
            self.coordinator.settings[SETTING_MODE] = DEFAULT_MODE
