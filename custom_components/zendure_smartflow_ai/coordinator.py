from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)


class ZendureSmartFlowCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.entry = entry
        self.entry_id = entry.entry_id   # ✅ DAS FEHLTE

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        # Dummy-Daten für jetzt
        return {
            "status": "ready",
            "reason": "initial_test"
        }
