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
# (IMMER vollständig halten!)
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
# AI / Betriebsmodi (Select-Entity)
# ==================================================
AI_MODE_ENTITY = "ai_mode"

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

# ==================================================
# Integration Settings (Number-Entities)
# ==================================================
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"

SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"

SETTING_PRICE_THRESHOLD = "price_threshold"
SETTING_PRICE_THRESHOLD_HIGH = "price_threshold_high"  # v0.5.x (Sehr teuer)

# ==================================================
# Default-Werte (Hersteller & Praxis)
# ==================================================
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0        # ✔ Hersteller- & Anwenderempfehlung
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0

DEFAULT_PRICE_THRESHOLD = 0.35       # „teuer“
DEFAULT_PRICE_THRESHOLD_HIGH = 0.49  # „sehr teuer“

# ==================================================
# Sensor-States / Debug
# ==================================================
AI_STATUS_STANDBY = "standby"
AI_STATUS_PV_SURPLUS = "pv_ueberschuss"
AI_STATUS_EXPENSIVE = "teuer"
AI_STATUS_VERY_EXPENSIVE = "sehr_teuer"
AI_STATUS_SENSOR_INVALID = "sensor_invalid"
AI_STATUS_PRICE_INVALID = "price_invalid"

# ==================================================
# Empfehlungen (Textlich)
# ==================================================
RECOMMENDATION_STANDBY = "standby"
RECOMMENDATION_CHARGE = "laden"
RECOMMENDATION_DISCHARGE = "entladen"
RECOMMENDATION_HOLD = "halten"

# ==================================================
# Backward Compatibility / Aliase
# (NIE entfernen!)
# ==================================================
DEFAULT_EXPENSIVE_THRESHOLD = DEFAULT_PRICE_THRESHOLD

# ==================================================
# Update / Timing
# ==================================================
UPDATE_INTERVAL = 10  # Sekunde
