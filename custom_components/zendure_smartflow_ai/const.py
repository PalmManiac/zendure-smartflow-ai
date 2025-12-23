# custom_components/zendure_smartflow_ai/const.py
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "zendure_smartflow_ai"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# -------------------------
# Config Flow Keys
# -------------------------
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"

# optional price export entity (Tibber data export)
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"

# Zendure / SolarFlow AC control entities
CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

# (optional future) grid sensor handling (kept for compatibility)
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# -------------------------
# Integration Settings (Number entities keys)
# -------------------------
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"
SETTING_EXPENSIVE_THRESHOLD = "expensive_threshold"
SETTING_VERY_EXPENSIVE_THRESHOLD = "very_expensive_threshold"
SETTING_SURPLUS_THRESHOLD = "surplus_threshold"

# -------------------------
# Defaults (no helpers required)
# -------------------------
DEFAULT_SOC_MIN = 12          # %
DEFAULT_SOC_MAX = 100         # % (Hersteller-/Anwenderempfehlung)
DEFAULT_MAX_CHARGE = 2000     # W
DEFAULT_MAX_DISCHARGE = 700   # W
DEFAULT_EXPENSIVE_THRESHOLD = 0.35        # €/kWh
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49   # €/kWh
DEFAULT_SURPLUS_THRESHOLD = 100           # W

# -------------------------
# AI Operation modes (Select)
# -------------------------
MODE_AUTOMATIC = "automatic"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_MANUAL = "manual"

AI_MODES = [MODE_AUTOMATIC, MODE_SUMMER, MODE_WINTER, MODE_MANUAL]

# Manual actions (Select)
MANUAL_STANDBY = "standby"
MANUAL_CHARGE = "charge"
MANUAL_DISCHARGE = "discharge"

MANUAL_ACTIONS = [MANUAL_STANDBY, MANUAL_CHARGE, MANUAL_DISCHARGE]

# -------------------------
# Coordinator behavior
# -------------------------
UPDATE_INTERVAL = 10  # seconds
FREEZE_SECONDS = 30   # keep short; freezes only text status/recommendation
