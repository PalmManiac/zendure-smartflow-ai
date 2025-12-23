from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "zendure_smartflow_ai"

# Platforms
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.NUMBER, Platform.SELECT]

# Update
UPDATE_INTERVAL = 10  # seconds

# -----------------------
# ConfigFlow keys
# -----------------------
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"

CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# -----------------------
# Internal settings keys (numbers/selects created by this integration)
# -----------------------
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"
SETTING_PRICE_THRESHOLD = "price_threshold"

# Defaults (no external helpers!)
DEFAULT_SOC_MIN = 12
DEFAULT_SOC_MAX = 100  # Herstellerempfehlung
DEFAULT_MAX_CHARGE = 2000
DEFAULT_MAX_DISCHARGE = 700
DEFAULT_PRICE_THRESHOLD = 0.35  # €/kWh

# -----------------------
# AI modes (select)
# -----------------------
AI_MODE_AUTO = "auto"
AI_MODE_SUMMER = "summer"
AI_MODE_WINTER = "winter"
AI_MODE_MANUAL = "manual"

AI_MODES = [AI_MODE_AUTO, AI_MODE_SUMMER, AI_MODE_WINTER, AI_MODE_MANUAL]

# Manual actions (select)
MANUAL_STANDBY = "standby"
MANUAL_CHARGE = "charge"
MANUAL_DISCHARGE = "discharge"

MANUAL_ACTIONS = [MANUAL_STANDBY, MANUAL_CHARGE, MANUAL_DISCHARGE]

# Device
DEVICE_NAME = "Zendure SmartFlow AI"
DEVICE_MANUFACTURER = "PalmManiac / Community"
DEVICE_MODEL = "SmartFlow AI"
