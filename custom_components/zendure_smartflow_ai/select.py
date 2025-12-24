from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SETTING_AI_MODE, SETTING_MANUAL_ACTION,
    AI_MODES, MANUAL_ACTIONS,
    AI_MODE_AUTOMATIC, MANUAL_STANDBY,
)
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True)
class ZSelectDescription(SelectEntityDescription):
    setting_key: str = ""
    default: str = ""
    options_list: list[str] | None = None


SELECTS: tuple[ZSelectDescription, ...] = (
    ZSelectDescription(
        key="ai_mode",
        name="Moduswahl",
        translation_key="ai_mode",
        icon="mdi:robot",
        setting_key=SETTING_AI_MODE,
        default=AI_MODE_AUTOMATIC,
        options_list=AI_MODES,
    ),
    ZSelectDescription(
        key="manual_action",
        name="Manuelle Aktion",
        translation_key="manual_action",
        icon="mdi:gesture-tap",
        setting_key=SETTING_MANUAL_ACTION,
        default=MANUAL_STANDBY,
        options_list=MANUAL_ACTIONS,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([ZendureSmartFlowSelect(coordinator, entry, d) for d in SELECTS])


class ZendureSmartFlowSelect(CoordinatorEntity[ZendureSmartFlowCoordinator], SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry, desc: ZSelectDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = desc
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "PalmManiac",
            "model": "SmartFlow AI",
        }
        self._attr_options = desc.options_list or []

    @property
    def current_option(self) -> str | None:
        v = self._entry.options.get(self.entity_description.setting_key, self.entity_description.default)
        s = str(v) if v is not None else self.entity_description.default
        return s

    async def async_select_option(self, option: str) -> None:
        new_opts = dict(self._entry.options)
        new_opts[self.entity_description.setting_key] = option
        self.hass.config_entries.async_update_entry(self._entry, options=new_opts)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
