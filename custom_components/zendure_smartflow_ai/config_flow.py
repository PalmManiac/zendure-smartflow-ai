from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import DOMAIN


class ZendureSmartFlowAIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow für Zendure SmartFlow AI"""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title="Zendure SmartFlow AI",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(
                    "soc_entity",
                    description={
                        "suggested_value": "sensor.solarflow_2400_ac_electric_level"
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="battery",
                    )
                ),

                vol.Required(
                    "price_export_entity",
                    description={
                        "suggested_value": "sensor.paul_schneider_strasse_39_diagramm_datenexport"
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor"
                    )
                ),

                vol.Required(
                    "battery_kwh",
                    default=5.76,
                ): vol.Coerce(float),

                vol.Required(
                    "soc_min",
                    default=12,
                ): vol.Coerce(float),

                vol.Required(
                    "soc_max",
                    default=95,
                ): vol.Coerce(float),

                vol.Required(
                    "cheap_threshold",
                    default=0.15,
                ): vol.Coerce(float),

                vol.Required(
                    "expensive_threshold",
                    default=0.35,
                ): vol.Coerce(float),

                vol.Required(
                    "max_charge",
                    default=2000,
                ): vol.Coerce(int),

                vol.Required(
                    "max_discharge",
                    default=700,
                ): vol.Coerce(int),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
