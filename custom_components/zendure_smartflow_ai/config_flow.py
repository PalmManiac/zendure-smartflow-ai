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
    CONF_DEVICE_PROFILE,
    DEVICE_PROFILE_SF2400AC,
    DEVICE_PROFILE_SF800PRO,
    DEFAULT_DEVICE_PROFILE,
)


class ZendureSmartFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Zendure SmartFlow AI."""

    VERSION = 1

    # -----------------------------------------------------
    # INITIAL SETUP
    # -----------------------------------------------------
    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._user_input = user_input
            return await self.async_step_grid()

        return self.async_show_form(
            step_id="user",
            data_schema=self._base_schema(),
        )

    async def async_step_grid(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        grid_mode = self._user_input.get(CONF_GRID_MODE, GRID_MODE_NONE)

        if user_input is not None:
            self._user_input.update(user_input)

            if grid_mode == GRID_MODE_SPLIT:
                if not user_input.get(CONF_GRID_IMPORT_ENTITY) or not user_input.get(CONF_GRID_EXPORT_ENTITY):
                    errors["base"] = "grid_split_missing"

            if not errors:
                return self.async_create_entry(
                    title="Zendure SmartFlow AI",
                    data=self._user_input,
                )

        return self.async_show_form(
            step_id="grid",
            data_schema=self._grid_schema(grid_mode),
            errors=errors,
        )

    # -----------------------------------------------------
    # RECONFIGURE
    # -----------------------------------------------------
    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._user_input = dict(entry.data)
            self._user_input.update(user_input)
            return await self.async_step_reconfigure_grid()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._base_schema(entry),
        )

    async def async_step_reconfigure_grid(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        grid_mode = self._user_input.get(CONF_GRID_MODE, GRID_MODE_NONE)

        if user_input is not None:
            cleaned = dict(self._user_input)
            cleaned.update(user_input)

            if grid_mode != GRID_MODE_SINGLE:
                cleaned.pop(CONF_GRID_POWER_ENTITY, None)
            if grid_mode != GRID_MODE_SPLIT:
                cleaned.pop(CONF_GRID_IMPORT_ENTITY, None)
                cleaned.pop(CONF_GRID_EXPORT_ENTITY, None)

            if grid_mode == GRID_MODE_SPLIT:
                if not cleaned.get(CONF_GRID_IMPORT_ENTITY) or not cleaned.get(CONF_GRID_EXPORT_ENTITY):
                    errors["base"] = "grid_split_missing"

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=cleaned,
                    reason="reconfigure_success",
                )

        return self.async_show_form(
            step_id="reconfigure_grid",
            data_schema=self._grid_schema(grid_mode, entry),
            errors=errors,
        )

    # -----------------------------------------------------
    # SCHEMAS
    # -----------------------------------------------------
    def _base_schema(self, entry: config_entries.ConfigEntry | None = None) -> vol.Schema:
        def _val(key: str):
            if entry:
                return entry.options.get(key, entry.data.get(key))
            return None

        return vol.Schema(
            {
                vol.Required(CONF_SOC_ENTITY, default=_val(CONF_SOC_ENTITY)):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),

                vol.Required(CONF_PV_ENTITY, default=_val(CONF_PV_ENTITY)):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),

                vol.Optional(CONF_PRICE_EXPORT_ENTITY, default=_val(CONF_PRICE_EXPORT_ENTITY)):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),

                vol.Optional(CONF_PRICE_NOW_ENTITY, default=_val(CONF_PRICE_NOW_ENTITY)):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),

                vol.Required(CONF_AC_MODE_ENTITY, default=_val(CONF_AC_MODE_ENTITY)):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="select")),

                vol.Required(CONF_INPUT_LIMIT_ENTITY, default=_val(CONF_INPUT_LIMIT_ENTITY)):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),

                vol.Required(CONF_OUTPUT_LIMIT_ENTITY, default=_val(CONF_OUTPUT_LIMIT_ENTITY)):
                    selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),

                vol.Required(CONF_GRID_MODE, default=_val(CONF_GRID_MODE) or GRID_MODE_SINGLE):
                    selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": GRID_MODE_NONE, "label": "Kein Netzsensor"},
                                {"value": GRID_MODE_SINGLE, "label": "Ein Sensor (+ / −)"},
                                {"value": GRID_MODE_SPLIT, "label": "Zwei Sensoren (Bezug & Einspeisung)"},
                            ]
                        )
                    ),
            }
        )

    def _grid_schema(
        self,
        grid_mode: str,
        entry: config_entries.ConfigEntry | None = None,
    ) -> vol.Schema:
        def _val(key: str):
            if entry:
                return entry.options.get(key, entry.data.get(key))
            return None

        schema: dict[Any, Any] = {}

        if grid_mode == GRID_MODE_SINGLE:
            schema[
                vol.Required(CONF_GRID_POWER_ENTITY, default=_val(CONF_GRID_POWER_ENTITY))
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        if grid_mode == GRID_MODE_SPLIT:
            schema[
                vol.Required(CONF_GRID_IMPORT_ENTITY, default=_val(CONF_GRID_IMPORT_ENTITY))
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
            schema[
                vol.Required(CONF_GRID_EXPORT_ENTITY, default=_val(CONF_GRID_EXPORT_ENTITY))
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

        return vol.Schema(schema)
