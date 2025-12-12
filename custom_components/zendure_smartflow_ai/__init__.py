from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ZendureSmartFlowCoordinator


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration via YAML (not used, but required)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zendure SmartFlow AI from a config entry."""

    coordinator = ZendureSmartFlowCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms (sensor, later switch, button, etc.)
    await hass.config_entries.async_forward_entry_setups(
        entry,
        ["sensor"]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        ["sensor"]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
