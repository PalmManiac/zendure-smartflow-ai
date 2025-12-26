from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector, entity_registry as er

from .const import (
    DOMAIN,
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    GRID_MODE_NONE,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,
)


def _find_first_entity(
    hass: HomeAssistant,
    domain: str,
    device_class: str | None = None,
    unit: str | None = None,
) -> str | None:
    reg = er.async_get(hass)
    for ent in reg.entities.values():
        if ent.domain != domain:
            continue
        if device_class and ent.device_class != device_class:
            continue
        if unit and ent.unit_of_measurement != unit:
            continue
        return ent.entity_id
    return None


class ZendureSmartFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            grid_mode = user_input.get(CONF_GRID_MODE, GRID_MODE_NONE)
            if grid_mode == GRID_MODE_SPLIT:
                if not user_input.get(CONF_GRID_IMPORT_ENTITY) or not user_input.get(CONF_GRID_EXPORT_ENTITY):
                    errors["base"] = "grid_split_missing"
            return self.async_create_entry(title="Zendure SmartFlow AI", data=user_input)

        hass = self.hass

        soc_guess = _find_first_entity(hass, "sensor", "battery", "%")
        pv_guess = _find_first_entity(hass, "sensor", "power", "W")

        price_now_guess = _find_first_entity(hass, "sensor", None, "€/kWh")
        price_export_guess = None  # absichtlich leer; viele haben Tibber Export mit Attribut "data"

        schema = vol.Schema(
            {
                vol.Required(CONF_SOC_ENTITY, default=soc_guess): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_PV_ENTITY, default=pv_guess): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),

                # Grid optional – wir berechnen Hausverbrauch intern aus PV + Grid (wenn Grid gewählt)
                vol.Required(CONF_GRID_MODE, default=GRID_MODE_NONE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": GRID_MODE_NONE, "label": "Kein Netzsensor (nur PV / SoC)"},
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

                # Preisquellen optional
                vol.Optional(CONF_PRICE_EXPORT_ENTITY, default=price_export_guess): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_PRICE_NOW_ENTITY, default=price_now_guess): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),

                # Zendure Steuer-Entitäten
                vol.Required(CONF_AC_MODE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="select")
                ),
                vol.Required(CONF_INPUT_LIMIT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
                vol.Required(CONF_OUTPUT_LIMIT_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
