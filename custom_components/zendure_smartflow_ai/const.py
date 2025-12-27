from __future__ import annotations

from homeassistant.const import Platform

# ==================================================
# Domain / Integration info
# ==================================================
DOMAIN = "zendure_smartflow_ai"

INTEGRATION_NAME = "Zendure SmartFlow AI"
INTEGRATION_MANUFACTURER = "PalmManiac"
INTEGRATION_MODEL = "SmartFlow AI"
INTEGRATION_VERSION = "0.12.0"

# ==================================================
# Platforms
# ==================================================
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# ==================================================
# Update
# ==================================================
UPDATE_INTERVAL = 10  # seconds

# ==================================================
# Config Flow – entity selection
# ==================================================
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"

CONF_PRICE_EXPORT_ENTITY = "price_export_entity"   # optional (Tibber data export -> attributes.data list)
CONF_PRICE_NOW_ENTITY = "price_now_entity"         # optional direct €/kWh sensor

CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

# Grid setup (recommended, used to compute house load)
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"   # single sensor (+import / -export)
CONF_GRID_IMPORT_ENTITY = "grid_import_entity" # split import
CONF_GRID_EXPORT_ENTITY = "grid_export_entity" # split export

GRID_MODE_NONE = "none"
GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# ==================================================
# Runtime selects
# ==================================================
AI_MODE_AUTOMATIC = "automatic"
AI_MODE_SUMMER = "summer"
AI_MODE_WINTER = "winter"
AI_MODE_MANUAL = "manual"

AI_MODES: list[str] = [
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
]

MANUAL_STANDBY = "standby"
MANUAL_CHARGE = "charge"
MANUAL_DISCHARGE = "discharge"

MANUAL_ACTIONS: list[str] = [
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,
]

# ==================================================
# Number entities (settings)
# ==================================================
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"
SETTING_PRICE_THRESHOLD = "price_threshold"
SETTING_VERY_EXPENSIVE_THRESHOLD = "very_expensive_threshold"

DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0  # Herstellerempfehlung (SoC max default 100%)
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0
DEFAULT_PRICE_THRESHOLD = 0.35
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49

# Backward compatibility aliases (falls irgendwo noch alte Namen importiert werden)
DEFAULT_EXPENSIVE_THRESHOLD = DEFAULT_PRICE_THRESHOLD
VERY_EXPENSIVE_THRESHOLD = DEFAULT_VERY_EXPENSIVE_THRESHOLD

# ==================================================
# Status / AI enums (for enum sensors)
# ==================================================
STATUS_INIT = "init"
STATUS_OK = "ok"
STATUS_SENSOR_INVALID = "sensor_invalid"
STATUS_PRICE_INVALID = "price_invalid"
STATUS_ERROR = "error"

STATUS_OPTIONS = [
    STATUS_INIT,
    STATUS_OK,
    STATUS_SENSOR_INVALID,
    STATUS_PRICE_INVALID,
    STATUS_ERROR,
]

# AI status values (short, stable identifiers)
AI_STATUS_STANDBY = "standby"
AI_STATUS_PV_CHARGE = "pv_charge"
AI_STATUS_COVER_DEFICIT = "cover_deficit"
AI_STATUS_PRICE_PEAK = "price_peak"
AI_STATUS_MANUAL_ACTIVE = "manual_active"
AI_STATUS_WAITING = "waiting"

AI_STATUS_OPTIONS = [
    AI_STATUS_STANDBY,
    AI_STATUS_PV_CHARGE,
    AI_STATUS_COVER_DEFICIT,
    AI_STATUS_PRICE_PEAK,
    AI_STATUS_MANUAL_ACTIVE,
    AI_STATUS_WAITING,
]

RECOMMENDATION_STANDBY = "standby"
RECOMMENDATION_CHARGE = "charge"
RECOMMENDATION_DISCHARGE = "discharge"

RECOMMENDATION_OPTIONS = [
    RECOMMENDATION_STANDBY,
    RECOMMENDATION_CHARGE,
    RECOMMENDATION_DISCHARGE,
]
