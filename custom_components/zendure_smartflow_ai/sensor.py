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

PLANNING_STATUS_ENUMS = [
    "not_checked",
    "sensor_invalid",
    "planning_inactive_mode",
    "planning_blocked_soc_full",
    "planning_blocked_pv_surplus",
    "planning_no_price_now",
    "planning_no_price_data",
    "planning_no_peak_detected",
    "planning_peak_detected_insufficient_window",
    "planning_waiting_for_cheap_window",
    "planning_charge_now",
    "planning_last_chance",
]

# NEW: next-action enums (V1.3.0)
NEXT_ACTION_ENUMS = [
    "none",
    "planned_charge",
    "planned_discharge",
    "charging_active",
    "discharging_active",
    "manual_charge",
    "manual_discharge",
    "emergency_charge",
]


@dataclass(frozen=True, kw_only=True)
class ZendureSensorEntityDescription(SensorEntityDescription):
    runtime_key: str

    def __post_init__(self):
        if not self.key:
            raise ValueError(
                "ZendureSmartFlowSensor created without a key. "
                "This would result in *_none entity_id."
            )

SENSORS: tuple[ZendureSensorEntityDescription, ...] = (
    # --- ENUM sensors (translated) ---
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

    # --- NEW SENSOR (V1.3.0) ---
    ZendureSensorEntityDescription(
        key="next_action",
        translation_key="next_action",
        runtime_key="next_action",
        icon="mdi:clock-outline",
    ),

    # --- Debug / reasoning ---
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

    # --- Planning transparency ---
    ZendureSensorEntityDescription(
        key="planning_status",
        translation_key="planning_status",
        runtime_key="planning_status",
        icon="mdi:timeline-alert",
        device_class=SensorDeviceClass.ENUM,
        options=PLANNING_STATUS_ENUMS,
    ),
    ZendureSensorEntityDescription(
        key="planning_active",
        translation_key="planning_active",
        runtime_key="planning_active",
        icon="mdi:flash",
    ),
    ZendureSensorEntityDescription(
        key="planning_target_soc",
        translation_key="planning_target_soc",
        runtime_key="planning_target_soc",
        icon="mdi:battery-high",
        native_unit_of_measurement="%",
    ),
    ZendureSensorEntityDescription(
        key="planning_reason",
        translation_key="planning_reason",
        runtime_key="planning_reason",
        icon="mdi:text-long",
    ),

    # --- Numeric sensors ---
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

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # HARD SAFETY CHECK
    for d in SENSORS:
        if not d.key:
            raise RuntimeError(f"Sensor without key detected: {d}")

    entities = []
    for d in SENSORS:
        if not d.key:
            _LOGGER.error(
                "Zendure SmartFlow AI: SensorEntityDescription ohne key entdeckt – wird übersprungen: %s",
                d,
            )
            continue
        entities.append(ZendureSmartFlowSensor(entry, coordinator, d))

    add_entities(entities)

class ZendureSmartFlowSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator,
        description: ZendureSensorEntityDescription,
    ) -> None:
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
        details = data.get("details") or {}
        key = self.entity_description.runtime_key

        # Values that live in details
        if key in (
            "house_load",
            "price_now",
            "avg_charge_price",
            "profit_eur",
            "planning_status",
            "planning_active",
            "planning_target_soc",
            "planning_reason",
            "next_action",  # NEW
        ):
            return details.get(key)

        return data.get(key)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        details = data.get("details") or {}

        if self.entity_description.key in (
            "status",
            "ai_status",
            "recommendation",
            "decision_reason",
            "ai_debug",
            "planning_status",
            "planning_active",
            "planning_target_soc",
            "planning_reason",
            "next_action",  # NEW
        ):
            return details

        return None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
