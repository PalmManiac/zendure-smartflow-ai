from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    INTEGRATION_NAME,
    INTEGRATION_MANUFACTURER,
    INTEGRATION_MODEL,
    INTEGRATION_VERSION,
    STATUS_ENUMS,
    AI_STATUS_ENUMS,
    RECO_ENUMS,
)


@dataclass(frozen=True, kw_only=True)
class ZendureSensorEntityDescription(SensorEntityDescription):
    runtime_key: str


SENSORS: tuple[ZendureSensorEntityDescription, ...] = (
    # ENUM states -> translated via strings/de/fr "state" mapping
    ZendureSensorEntityDescription(
        key="status",
        translation_key="status",
        runtime_key="status",
        icon="mdi:power-plug",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_ENUMS,
    ),
    ZendureSensorEntityDescription(
        key="ai_status",
        translation_key="ai_status",
        runtime_key="ai_status",
        icon="mdi:robot",
        device_class=SensorDeviceClass.ENUM,
        options=AI_STATUS_ENUMS,
    ),
    ZendureSensorEntityDescription(
        key="recommendation",
        translation_key="recommendation",
        runtime_key="recommendation",
        icon="mdi:lightbulb-outline",
        device_class=SensorDeviceClass.ENUM,
        options=RECO_ENUMS,
    ),
    # Debug remains raw (string)
    ZendureSensorEntityDescription(
        key="ai_debug",
        translation_key="ai_debug",
        runtime_key="debug",
        icon="mdi:bug",
    ),
    ZendureSensorEntityDescription(
        key="decision_reason",
        translation_key="decision_reason",
        runtime_key="decision_reason",
        icon="mdi:head-question-outline",
    ),
    # Numeric sensors
    ZendureSensorEntityDescription(
        key="house_load",
        translation_key="house_load",
        runtime_key="house_load",
        icon="mdi:home-lightning-bolt",
        native_unit_of_measurement="W",
    ),
    ZendureSensorEntityDescription(
        key="price_now",
        translation_key="price_now",
        runtime_key="price_now",
        icon="mdi:currency-eur",
        native_unit_of_measurement="€/kWh",
    ),
    ZendureSensorEntityDescription(
        key="avg_charge_price",
        translation_key="avg_charge_price",
        runtime_key="avg_charge_price",
        icon="mdi:scale-balance",
        native_unit_of_measurement="€/kWh",
    ),
    ZendureSensorEntityDescription(
        key="profit_eur",
        translation_key="profit_eur",
        runtime_key="profit_eur",
        icon="mdi:cash",
        native_unit_of_measurement="€",
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    add_entities([ZendureSmartFlowSensor(entry, coordinator, d) for d in SENSORS])


class ZendureSmartFlowSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, coordinator, description: ZendureSensorEntityDescription) -> None:
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
    def native_value(self):
        data = self.coordinator.data or {}
        key = self.entity_description.runtime_key

        details = data.get("details") or {}

        if key == "house_load":
            return details.get("house_load")
        if key == "price_now":
            return details.get("price_now")
        if key == "avg_charge_price":
            return details.get("avg_charge_price")
        if key == "profit_eur":
            return details.get("profit_eur")

        return data.get(key)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        if self.entity_description.key in ("ai_status", "recommendation", "status", "ai_debug"):
            return data.get("details")
        return None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
