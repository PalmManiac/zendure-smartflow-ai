from __future__ import annotations

from homeassistant.const import Platform

# ==================================================
# Domain / Integration meta
# ==================================================
DOMAIN = "zendure_smartflow_ai"

INTEGRATION_NAME = "Zendure SmartFlow AI"
INTEGRATION_MANUFACTURER = "TK-Multimedia"
INTEGRATION_MODEL = "SmartFlow AI"
INTEGRATION_VERSION = "0.13.0"

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

# optional price sources
CONF_PRICE_NOW_ENTITY = "price_now_entity"          # direct price sensor (€/kWh)
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"    # Tibber export sensor (attributes.data)

# Zendure control entities
CONF_AC_MODE_ENTITY = "ac_mode_entity"              # select input/output
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"      # number W
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"    # number W

# Grid setup
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"        # single: +import / -export
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"      # split: import only
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"      # split: export only

GRID_MODE_NONE = "none"
GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

GRID_MODES = [GRID_MODE_NONE, GRID_MODE_SINGLE, GRID_MODE_SPLIT]

# ==================================================
# Internal "settings" (Number entities)
# ==================================================
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"
SETTING_VERY_EXPENSIVE_THRESHOLD = "very_expensive_threshold"
SETTING_PROFIT_MARGIN_PERCENT = "profit_margin_percent"

# ==================================================
# Defaults
# ==================================================
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0  # Hersteller/Community Empfehlung
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0

# "Sehr teuer" bleibt als Hard-Override
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49

# Gewinnmarge: ab wie viel % über Ø-Ladepreis soll entladen werden
DEFAULT_PROFIT_MARGIN_PERCENT = 25.0

# ==================================================
# Update interval
# ==================================================
UPDATE_INTERVAL = 10  # seconds

# ==================================================
# Runtime modes (Select entities) - internal values stay EN
# ==================================================
AI_MODE_AUTOMATIC = "automatic"
AI_MODE_SUMMER = "summer"
AI_MODE_WINTER = "winter"
AI_MODE_MANUAL = "manual"

AI_MODES = [AI_MODE_AUTOMATIC, AI_MODE_SUMMER, AI_MODE_WINTER, AI_MODE_MANUAL]

MANUAL_STANDBY = "standby"
MANUAL_CHARGE = "charge"
MANUAL_DISCHARGE = "discharge"

MANUAL_ACTIONS = [MANUAL_STANDBY, MANUAL_CHARGE, MANUAL_DISCHARGE]

# ==================================================
# Sensor enum values (internal)
# ==================================================
STATUS_INIT = "init"
STATUS_OK = "ok"
STATUS_SENSOR_INVALID = "sensor_invalid"
STATUS_PRICE_MISSING = "price_missing"

RECO_STANDBY = "standby"
RECO_CHARGE = "charge"
RECO_DISCHARGE = "discharge"

AI_STATUS_STANDBY = "standby"
AI_STATUS_CHARGE_SURPLUS = "charge_surplus"
AI_STATUS_COVER_DEFICIT = "cover_deficit"
AI_STATUS_VERY_EXPENSIVE = "very_expensive"
AI_STATUS_PROFIT_MARGIN = "profit_margin"
AI_STATUS_MANUAL = "manual"

ENUM_STATUS = [STATUS_INIT, STATUS_OK, STATUS_SENSOR_INVALID, STATUS_PRICE_MISSING]
ENUM_AI_STATUS = [
    AI_STATUS_STANDBY,
    AI_STATUS_CHARGE_SURPLUS,
    AI_STATUS_COVER_DEFICIT,
    AI_STATUS_VERY_EXPENSIVE,
    AI_STATUS_PROFIT_MARGIN,
    AI_STATUS_MANUAL,
]
ENUM_RECOMMENDATION = [RECO_STANDBY, RECO_CHARGE, RECO_DISCHARGE]
