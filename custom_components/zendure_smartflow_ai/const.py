# custom_components/zendure_smartflow_ai/const.py
from __future__ import annotations

from homeassistant.const import Platform

# ==================================================
# Integration Meta
# ==================================================
DOMAIN = "zendure_smartflow_ai"

INTEGRATION_NAME = "Zendure SmartFlow AI"
INTEGRATION_MANUFACTURER = "PalmManiac"
INTEGRATION_MODEL = "SmartFlow AI"
INTEGRATION_VERSION = "0.11.0"

# ==================================================
# Platforms
# ==================================================
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# ==================================================
# Config-Flow: Entity Auswahl
# (DIESE KEYS DÜRFEN NIE ENTFERNT WERDEN)
# ==================================================
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"

CONF_PRICE_EXPORT_ENTITY = "price_export_entity"
CONF_PRICE_NOW_ENTITY = "price_now_entity"

CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

# Grid (optional / legacy)
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

# ==================================================
# Grid Modes (inkl. Legacy / None)
# ==================================================
GRID_MODE_NONE = "none"
GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# ==================================================
# Runtime / Settings Keys (Integration-eigene Entitäten)
# ==================================================
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"
SETTING_PRICE_THRESHOLD = "price_threshold"
SETTING_VERY_EXPENSIVE_THRESHOLD = "very_expensive_threshold"

# ==================================================
# Defaults
# ==================================================
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0          # Herstellerempfehlung ✔
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0

DEFAULT_EXPENSIVE_THRESHOLD = 0.35
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49

# ==================================================
# Backward compatibility / Aliases
# ==================================================
DEFAULT_PRICE_THRESHOLD = DEFAULT_EXPENSIVE_THRESHOLD
VERY_EXPENSIVE_THRESHOLD = DEFAULT_VERY_EXPENSIVE_THRESHOL

# ==================================================
# Update / Timing
# ==================================================
UPDATE_INTERVAL = 10  # Sekunden

# ==================================================
# AI Modes / Manual Actions (Runtime)
# ==================================================
AI_MODE_AUTOMATIC = "automatic"
AI_MODE_SUMMER = "summer"
AI_MODE_WINTER = "winter"
AI_MODE_MANUAL = "manual"

AI_MODES = [
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
]

MANUAL_STANDBY = "standby"
MANUAL_CHARGE = "charge"
MANUAL_DISCHARGE = "discharge"

MANUAL_ACTIONS = [
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
]
