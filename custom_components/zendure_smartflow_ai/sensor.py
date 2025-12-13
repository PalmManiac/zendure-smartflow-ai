from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator

_LOGGER = logging.getLogger(__name__)

# Cache: lang -> dict (geladen aus translations/<lang>.json)
_TRANSLATION_CACHE: dict[str, dict[str, Any]] = {}


async def _async_load_translation(hass: HomeAssistant, lang: str) -> dict[str, Any]:
    """Load translation JSON from disk using executor (non-blocking for event loop)."""
    if lang in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[lang]

    path = Path(__file__).parent / "translations" / f"{lang}.json"

    def _read() -> dict[str, Any]:
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8")
        return json.loads(text)

    try:
        data = await hass.async_add_executor_job(_read)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not load translation %s: %s", lang, err)
        data = {}

    _TRANSLATION_CACHE[lang] = data
    return data


def _t(hass: HomeAssistant, domain: str, key: str) -> str:
    """
    Translate helper. Reads only from cache.
    Falls nichts gefunden: key zurückgeben (damit nie Exceptions).
    """
    lang = getattr(hass.config, "language", None) or "en"
    data = _TRANSLATION_CACHE.get(lang) or _TRANSLATION_CACHE.get("en") or {}

    # erwartete Struktur: {"entity": {"sensor": {"ai_status": {"state": {...}}}}}
    try:
        return (
            data.get("entity", {})
            .get("sensor", {})
            .get(domain, {})
            .get("state", {})
            .get(key, key)
        )
    except Exception:  # noqa: BLE001
        return key


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Set up sensors for this config entry."""
    coordinator: ZendureSmartFlowCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Übersetzungen 1x laden (nicht in Properties!)
    await _async_load_translation(hass, "en")
    await _async_load_translation(hass, getattr(hass.config, "language", "en"))

    async_add_entities(
        [
            ZendureSmartFlowStatusSensor(coordinator, entry),
            ZendureSmartFlowRecommendationSensor(coordinator, entry),
            ZendureSmartFlowDebugSensor(coordinator, entry),
        ]
    )


class _BaseZendureSensor(CoordinatorEntity[ZendureSmartFlowCoordinator], SensorEntity):
    """Base class with common device info / unique_id handling."""

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or "Zendure SmartFlow AI",
            "manufacturer": "PalmManiac",
            "model": "Zendure SmartFlow AI",
        }


class ZendureSmartFlowStatusSensor(_BaseZendureSensor):
    _attr_name = "Zendure SmartFlow AI Status"
    _attr_icon = "mdi:brain"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_ai_status"

    @property
    def native_value(self) -> str:
        return (self.coordinator.data or {}).get("ai_status", "unknown")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        key = (self.coordinator.data or {}).get("ai_status", "unknown")
        return {
            "status_text": _t(self.hass, "ai_status", key),
        }


class ZendureSmartFlowRecommendationSensor(_BaseZendureSensor):
    _attr_name = "Zendure Akku Steuerungsempfehlung"
    _attr_icon = "mdi:robot"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_recommendation"

    @property
    def native_value(self) -> str:
        return (self.coordinator.data or {}).get("recommendation", "standby")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        key = (self.coordinator.data or {}).get("recommendation", "standby")
        return {
            "recommendation_text": _t(self.hass, "recommendation", key),
        }


class ZendureSmartFlowDebugSensor(_BaseZendureSensor):
    _attr_name = "Zendure SmartFlow AI Debug"
    _attr_icon = "mdi:bug-outline"

    def __init__(self, coordinator: ZendureSmartFlowCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_debug"

    @property
    def native_value(self) -> str:
        # Debug als kurzer Text (State max 255 beachten!)
        dbg = (self.coordinator.data or {}).get("debug", "")
        if dbg is None:
            return ""
        return str(dbg)[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        # Hier dürfen beliebige Attribute rein (Attribute-Limit ist deutlich höher als State)
        return {
            "ai_status": data.get("ai_status"),
            "recommendation": data.get("recommendation"),
            "price_now": data.get("price_now"),
            "expensive_threshold": data.get("expensive_threshold"),
            "details": data.get("details", {}),
        }
