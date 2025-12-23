from __future__ import annotations

from homeassistant.const import Platform

# ==================================================
# Domain
# ==================================================
DOMAIN = "zendure_smartflow_ai"

# ==================================================
# Platforms
# ==================================================
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# ==================================================
# Config Flow – Entity Auswahl
# ==================================================
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"

CONF_PRICE_NOW_ENTITY = "price_now_entity"
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"

CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

# ==================================================
# Grid / Hausanschluss
# ==================================================
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# ==================================================
# Integration Settings (Number-Entities)
# ==================================================
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"
SETTING_PRICE_THRESHOLD = "price_threshold"

# ==================================================
# Default-Werte (stabil & Herstellerkonform)
# ==================================================
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0        # ✔ Hersteller- & Community-Empfehlung
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0

DEFAULT_EXPENSIVE_THRESHOLD = 0.35

# ==================================================
# Backward / Alias-Kompatibilität
# (verhindert NameError bei älteren Codestellen)
# ==================================================
DEFAULT_PRICE_THRESHOLD = DEFAULT_EXPENSIVE_THRESHOLD
DEFAULT_EXPENSIVE = DEFAULT_EXPENSIVE_THRESHOLD
