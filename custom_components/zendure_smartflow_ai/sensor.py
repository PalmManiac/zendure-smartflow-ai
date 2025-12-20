from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


@dataclass(frozen=True, kw_only=True)
class _Desc(SensorEntityDescription):
    key: str


SENSORS: tuple[_Desc, ...] = (
    _Desc(
        key="ai_status",
        name="Zendure SmartFlow AI Status",
        icon="mdi:robot",
    ),
    _Desc(
        key="recommendation",
        name="Zendure SmartFlow AI Steuerungsempfehlung",
        icon="mdi:lightbulb-auto",
    ),
    _Desc(
        key="debug",
        name="Zendure SmartFlow AI Debug",
        icon="mdi:bug-outline",
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ZendureSmartFlowSensor(coordinator, entry, d) for d in SENSORS])


class ZendureSmartFlowSensor(SensorEntity):
    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry, desc: _Desc) -> None:
        self.coordinator = coordinator
        self.entity_description = desc
        self._attr_unique_id = f"{entry.entry_id}_{desc.key}"
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry_id)},
            "name": "Zendure SmartFlow AI",
            "manufacturer": "PalmManiac",
            "model": "SmartFlow AI",
        }

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        v = data.get(self.entity_description.key)
        if v is None:
            return ""
        # state length safety for debug
        s = str(v)
        return s[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return data.get("details", {})
