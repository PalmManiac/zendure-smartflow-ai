from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    GRID_MODE_NONE,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
)


class ZendureSmartFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Zendure SmartFlow AI."""

    VERSION = 1

    # -----------------------------------------------------
    # INITIAL SETUP (Add integration)
    # -----------------------------------------------------
    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = dict(user_input)
            grid_mode = user_input.get(CONF_GRID_MODE, GRID_MODE_NONE)

            # --- validation ---
            if grid_mode == GRID_MODE_SPLIT:
                if not user_input.get(CONF_GRID_IMPORT_ENTITY) or not user_input.get(CONF_GRID_EXPORT_ENTITY):
                    errors["base"] = "grid_split_missing"

            # --- HARD CLEANUP (IMPORTANT) ---
            if not errors:
                if grid_mode == GRID_MODE_SPLIT:
                    user_input.pop(CONF_GRID_POWER_ENTITY, None)

                elif grid_mode == GRID_MODE_SINGLE:
                    user_input.pop(CONF_GRID_IMPORT_ENTITY, None)
                    user_input.pop(CONF_GRID_EXPORT_ENTITY, None)

                elif grid_mode == GRID_MODE_NONE:
                    user_input.pop(CONF_GRID_POWER_ENTITY, None)
                    user_input.pop(CONF_GRID_IMPORT_ENTITY, None)
                    user_input.pop(CONF_GRID_EXPORT_ENTITY, None)

                return self.async_create_entry(
                    title="Zendure SmartFlow AI",
                    data=user_input,
                )

        schema = self._build_schema()

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    # -----------------------------------------------------
    # RECONFIGURE (Configure → change entities later)
    # -----------------------------------------------------
    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        entry = self._get_reconfigure_entry()

        if user_input is not None:
            user_input = dict(user_input)
            grid_mode = user_input.get(CONF_GRID_MODE, GRID_MODE_NONE)

            # --- validation ---
            if grid_mode == GRID_MODE_SPLIT:
                if not user_input.get(CONF_GRID_IMPORT_ENTITY) or not user_input.get(CONF_GRID_EXPORT_ENTITY):
                    errors["base"] = "grid_split_missing"

            # --- HARD CLEANUP (IMPORTANT) ---
            if not errors:
                if grid_mode == GRID_MODE_SPLIT:
                    user_input.pop(CONF_GRID_POWER_ENTITY, None)

                elif grid_mode == GRID_MODE_SINGLE:
                    user_input.pop(CONF_GRID_IMPORT_ENTITY, None)
                    user_input.pop(CONF_GRID_EXPORT_ENTITY, None)

                elif grid_mode == GRID_MODE_NONE:
                    user_input.pop(CONF_GRID_POWER_ENTITY, None)
                    user_input.pop(CONF_GRID_IMPORT_ENTITY, None)
                    user_input.pop(CONF_GRID_EXPORT_ENTITY, None)

                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                    reason="reconfigure_success",
                )

        schema = self._build_schema(entry)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )

    # -----------------------------------------------------
    # Helpers
    # -----------------------------------------------------
    def _build_schema(self, entry: config_entries.ConfigEntry | None = None) -> vol.Schema:
        """Build schema for setup & reconfigure."""

        def _val(key: str):
            if entry is None:
                return None
            return entry.options.get(key, entry.data.get(key))

        return vol.Schema(
            {
                vol.Required(CONF_SOC_ENTITY, default=_val(CONF_SOC_ENTITY)):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),

                vol.Required(CONF_PV_ENTITY, default=_val(CONF_PV_ENTITY)):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),

                vol.Optional(CONF_PRICE_EXPORT_ENTITY, default=_val(CONF_PRICE_EXPORT_ENTITY)):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),

                vol.Optional(CONF_PRICE_NOW_ENTITY, default=_val(CONF_PRICE_NOW_ENTITY)):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),

                vol.Required(CONF_AC_MODE_ENTITY, default=_val(CONF_AC_MODE_ENTITY)):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="select")
                    ),

                vol.Required(CONF_INPUT_LIMIT_ENTITY, default=_val(CONF_INPUT_LIMIT_ENTITY)):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="number")
                    ),

                vol.Required(CONF_OUTPUT_LIMIT_ENTITY, default=_val(CONF_OUTPUT_LIMIT_ENTITY)):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="number")
                    ),

                vol.Optional(CONF_GRID_MODE, default=_val(CONF_GRID_MODE) or GRID_MODE_SINGLE):
                    selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": GRID_MODE_NONE, "label": "Kein Netzsensor"},
                                {"value": GRID_MODE_SINGLE, "label": "Ein Sensor (+ Bezug / – Einspeisung)"},
                                {"value": GRID_MODE_SPLIT, "label": "Zwei Sensoren (Bezug & Einspeisung getrennt)"},
                            ]
                        )
                    ),

                vol.Optional(CONF_GRID_POWER_ENTITY, default=_val(CONF_GRID_POWER_ENTITY)):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),

                vol.Optional(CONF_GRID_IMPORT_ENTITY, default=_val(CONF_GRID_IMPORT_ENTITY)):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),

                vol.Optional(CONF_GRID_EXPORT_ENTITY, default=_val(CONF_GRID_EXPORT_ENTITY)):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
            }
        )
