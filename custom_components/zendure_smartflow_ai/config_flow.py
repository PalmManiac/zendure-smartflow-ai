from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_LOAD_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
)


class ZendureSmartFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(
                title="Zendure SmartFlow AI",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_SOC_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_PV_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_LOAD_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_PRICE_EXPORT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_AC_MODE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="select")
                ),
                vol.Required(CONF_GRID_MODE, default=GRID_MODE_SINGLE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": GRID_MODE_SINGLE, "label": "Ein Sensor (+ Bezug / – Einspeisung)"},
                            {"value": GRID_MODE_SPLIT, "label": "Zwei Sensoren (Bezug & Einspeisung getrennt)"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_GRID_POWER_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_GRID_IMPORT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_GRID_EXPORT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)
