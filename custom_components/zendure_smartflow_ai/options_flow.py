from __future__ import annotations
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import *


class ZendureSmartFlowOptionsFlow(config_entries.OptionsFlow):
    """Options flow to update external entities without reinstallation."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            grid_mode = user_input.get(CONF_GRID_MODE, GRID_MODE_NONE)

            if grid_mode == GRID_MODE_SPLIT:
                if not user_input.get(CONF_GRID_IMPORT_ENTITY) or not user_input.get(CONF_GRID_EXPORT_ENTITY):
                    errors["base"] = "grid_split_missing"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        def _opt(key: str):
            return self.config_entry.options.get(key, self.config_entry.data.get(key))

        schema_dict = {}

        # REQUIRED entities – only if default exists
        for key, domain in [
            (CONF_SOC_ENTITY, "sensor"),
            (CONF_PV_ENTITY, "sensor"),
            (CONF_AC_MODE_ENTITY, "select"),
            (CONF_INPUT_LIMIT_ENTITY, "number"),
            (CONF_OUTPUT_LIMIT_ENTITY, "number"),
        ]:
            default = _opt(key)
            if default is not None:
                schema_dict[vol.Required(key, default=default)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=domain)
                )
            else:
                schema_dict[vol.Optional(key)] = selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=domain)
                )

        # Optional price sensors
        for key in (CONF_PRICE_EXPORT_ENTITY, CONF_PRICE_NOW_ENTITY):
            default = _opt(key)
            schema_dict[vol.Optional(key, default=default)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        # Grid mode
        schema_dict[
            vol.Optional(CONF_GRID_MODE, default=_opt(CONF_GRID_MODE) or GRID_MODE_SINGLE)
        ] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": GRID_MODE_NONE, "label": "Kein Netzsensor"},
                    {"value": GRID_MODE_SINGLE, "label": "Ein Sensor"},
                    {"value": GRID_MODE_SPLIT, "label": "Zwei Sensoren"},
                ]
            )
        )

        # Grid sensors
        for key in (CONF_GRID_POWER_ENTITY, CONF_GRID_IMPORT_ENTITY, CONF_GRID_EXPORT_ENTITY):
            default = _opt(key)
            schema_dict[vol.Optional(key, default=default)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )
