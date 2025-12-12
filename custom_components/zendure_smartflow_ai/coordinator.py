from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


class ZendureSmartFlowCoordinator(DataUpdateCoordinator):
    """Coordinator for Zendure SmartFlow AI."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""

        self.entry = entry
        self.entry_id = entry.entry_id 

        super().__init__(
            hass,
            LOGGER,  # ✅ GANZ WICHTIG
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        """
        Fetch data for all sensors.

        Hier kommt später:
        - Tibber Preise
        - SoC
        - Status-Logik
        """

        # Platzhalter – verhindert weitere Fehler
        return {}
