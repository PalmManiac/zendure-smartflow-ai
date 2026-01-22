from __future__ import annotations

from homeassistant.const import Platform

# ==================================================
# Integration meta
# ==================================================
DOMAIN = "zendure_smartflow_ai"

INTEGRATION_NAME = "Zendure SmartFlow AI"
INTEGRATION_MANUFACTURER = "PalmManiac"
INTEGRATION_MODEL = "Home Assistant Integration"
INTEGRATION_VERSION = "1.4.0-Beta6"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# ==================================================
# Config Flow – required/optional entities
# ==================================================
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"

# Preis ist optional (Sommer/PV-only Nutzer)
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"  # Tibber Export (attributes.data)
CONF_PRICE_NOW_ENTITY = "price_now_entity"        # direkter Preis-Sensor (€/kWh)

# Zendure Steuer-Entitäten
CONF_AC_MODE_ENTITY = "ac_mode_entity"            # select input/output
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"    # number W
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"  # number W

# Grid Setup (empfohlen, weil wir daraus den Hausverbrauch intern berechnen)
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"      # +import / -export
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"    # import W
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"    # export W

GRID_MODE_NONE = "none"
GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# ==================================================
# Runtime select modes (internal values remain EN)
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
# Settings (Number entities) – entity keys
# ==================================================
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"

SETTING_PRICE_THRESHOLD = "price_threshold"
SETTING_VERY_EXPENSIVE_THRESHOLD = "very_expensive_threshold"

SETTING_EMERGENCY_SOC = "emergency_soc"           # Notladung wenn SoC <= x
SETTING_EMERGENCY_CHARGE = "emergency_charge"     # Notladeleistung (W)

SETTING_PROFIT_MARGIN_PCT = "profit_margin_pct"   # Arbitrage/Planung

# ==================================================
# Defaults
# ==================================================
UPDATE_INTERVAL = 10  # seconds

DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0  # Herstellerempfehlung ✔

DEFAULT_MAX_CHARGE = 2400.0
DEFAULT_MAX_DISCHARGE = 700.0

DEFAULT_PRICE_THRESHOLD = 0.35
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49

DEFAULT_EMERGENCY_SOC = 8.0
DEFAULT_EMERGENCY_CHARGE = 1200.0

DEFAULT_PROFIT_MARGIN_PCT = 27.0

# ==================================================
# Status / Enum values (internal)
# ==================================================
STATUS_INIT = "init"
STATUS_OK = "ok"
STATUS_SENSOR_INVALID = "sensor_invalid"
STATUS_PRICE_INVALID = "price_invalid"

AI_STATUS_STANDBY = "standby"
AI_STATUS_CHARGE_SURPLUS = "charge_surplus"
AI_STATUS_COVER_DEFICIT = "cover_deficit"
AI_STATUS_EXPENSIVE_DISCHARGE = "expensive_discharge"
AI_STATUS_VERY_EXPENSIVE_FORCE = "very_expensive_force"
AI_STATUS_EMERGENCY_CHARGE = "emergency_charge"
AI_STATUS_MANUAL = "manual"

RECO_STANDBY = "standby"
RECO_CHARGE = "charge"
RECO_DISCHARGE = "discharge"
RECO_EMERGENCY = "emergency_charge"

STATUS_ENUMS = [
    STATUS_INIT,
    STATUS_OK,
    STATUS_SENSOR_INVALID,
    STATUS_PRICE_INVALID,
]

AI_STATUS_ENUMS = [
    AI_STATUS_STANDBY,
    AI_STATUS_CHARGE_SURPLUS,
    AI_STATUS_COVER_DEFICIT,
    AI_STATUS_EXPENSIVE_DISCHARGE,
    AI_STATUS_VERY_EXPENSIVE_FORCE,
    AI_STATUS_EMERGENCY_CHARGE,
    AI_STATUS_MANUAL,
]

RECO_ENUMS = [
    RECO_STANDBY,
    RECO_CHARGE,
    RECO_DISCHARGE,
    RECO_EMERGENCY,
]

# ==================================================
# Planning enums (V1.4.0)
# ==================================================
NEXT_ACTION_STATE_ENUMS = [
    "none",
    "planned_charge",
    "planned_discharge",
    "charging_active",
    "discharging_active",
    "manual_charge",
    "manual_discharge",
    "emergency_charge",
]

NEXT_PLANNED_ACTION_ENUMS = [
    "none",
    "charge",
    "discharge",
    "wait",
    "emergency",
]

# ==================================================
# Zendure AC Mode options
# ==================================================
ZENDURE_MODE_INPUT = "input"
ZENDURE_MODE_OUTPUT = "output"
