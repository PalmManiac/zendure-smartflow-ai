from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN


# =========================
# Netzwerk-Messart
# =========================
GRID_MODE_SINGLE = "single_sensor"
GRID_MODE_SPLIT = "split_sensors"


class ZendureSmartFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow für Zendure SmartFlow AI (V0.1.1 Minimal-Fix)."""

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
                # =========================
                # Pflicht-Sensoren
                # =========================
                vol.Required("soc_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required("pv_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required("load_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),

                # =========================
                # Preis
                # =========================
                vol.Required("price_now_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),

                # =========================
                # Netz-Messart
                # =========================
                vol.Required("grid_mode", default=GRID_MODE_SINGLE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": GRID_MODE_SINGLE, "label": "Ein Sensor (± Bezug/Einspeisung)"},
                            {"value": GRID_MODE_SPLIT, "label": "Getrennte Sensoren (Bezug / Einspeisung)"},
                        ],
                        mode="dropdown",
                    )
                ),

                # =========================
                # Netz-Sensoren
                # =========================
                vol.Optional("grid_power_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("grid_import_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("grid_export_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),

                # =========================
                # Zendure Steuerung
                # =========================
                vol.Required("ac_mode_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="select")
                ),
                vol.Required("input_limit_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
                vol.Required("output_limit_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ZendureSmartFlowOptionsFlow(config_entry)


class ZendureSmartFlowOptionsFlow(config_entries.OptionsFlow):
    """Options Flow (identisch zu Setup, für spätere Anpassungen)."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.config_entry.data

        schema = vol.Schema(
            {
                vol.Required("soc_entity", default=data.get("soc_entity")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required("pv_entity", default=data.get("pv_entity")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required("load_entity", default=data.get("load_entity")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required("price_now_entity", default=data.get("price_now_entity")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required("grid_mode", default=data.get("grid_mode")): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": GRID_MODE_SINGLE, "label": "Ein Sensor (± Bezug/Einspeisung)"},
                            {"value": GRID_MODE_SPLIT, "label": "Getrennte Sensoren (Bezug / Einspeisung)"},
                        ],
                        mode="dropdown",
                    )
                ),
                vol.Optional("grid_power_entity", default=data.get("grid_power_entity")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("grid_import_entity", default=data.get("grid_import_entity")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional("grid_export_entity", default=data.get("grid_export_entity")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required("ac_mode_entity", default=data.get("ac_mode_entity")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="select")
                ),
                vol.Required("input_limit_entity", default=data.get("input_limit_entity")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
                vol.Required("output_limit_entity", default=data.get("output_limit_entity")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
