from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "zendure_smartflow_ai"

# Anzeige in Geräte-Info (Manufacturer / Model / SW-Version)
INTEGRATION_MANUFACTURER = "PalmManiac"
INTEGRATION_MODEL = "Zendure SmartFlow AI"
INTEGRATION_NAME = "Zendure SmartFlow AI"
INTEGRATION_VERSION = "0.10.0"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# -------------------------
# Config-Flow Keys
# -------------------------
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"

CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

CONF_PRICE_EXPORT_ENTITY = "price_export_entity"
CONF_PRICE_NOW_ENTITY = "price_now_entity"

CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

GRID_MODE_NONE = "none"
GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# -------------------------
# Integration Settings (Number-Entities keys)
# -------------------------
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"
SETTING_PRICE_THRESHOLD = "price_threshold"
SETTING_VERY_EXPENSIVE_THRESHOLD = "very_expensive_threshold"

# -------------------------
# Defaults
# -------------------------
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0  # Herstellerempfehlung ✔
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0

DEFAULT_PRICE_THRESHOLD = 0.35
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49

UPDATE_INTERVAL = 10

# -------------------------
# Select options (internal keys)
# -------------------------
AI_MODE_AUTOMATIC = "automatic"
AI_MODE_SUMMER = "summer"
AI_MODE_WINTER = "winter"
AI_MODE_MANUAL = "manual"

MANUAL_STANDBY = "standby"
MANUAL_CHARGE = "charge"
MANUAL_DISCHARGE = "discharge"

AI_MODES = [AI_MODE_AUTOMATIC, AI_MODE_SUMMER, AI_MODE_WINTER, AI_MODE_MANUAL]
MANUAL_ACTIONS = [MANUAL_STANDBY, MANUAL_CHARGE, MANUAL_DISCHARGE]

# -------------------------
# Sensor states (internal keys; werden über translations als Enum angezeigt)
# -------------------------
STATUS_INIT = "init"
STATUS_OK = "ok"
STATUS_ERROR = "error"

AI_STATUS_STANDBY = "standby"
AI_STATUS_PRICE_INVALID = "price_invalid"
AI_STATUS_SENSOR_INVALID = "sensor_invalid"
AI_STATUS_VERY_EXPENSIVE = "very_expensive"
AI_STATUS_EXPENSIVE = "expensive"
AI_STATUS_PV_SURPLUS = "pv_surplus"
AI_STATUS_MANUAL = "manual"
AI_STATUS_CHARGE = "charge"
AI_STATUS_DISCHARGE = "discharge"
