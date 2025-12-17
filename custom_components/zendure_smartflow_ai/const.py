DOMAIN = "zendure_smartflow_ai"

# =========================
# Config Keys
# =========================

CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"
CONF_PRICE_NOW_ENTITY = "price_now_entity"

CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

CONF_AC_MODE_ENTITY = "ac_mode_entity"

CONF_SOC_MIN = "soc_min"
CONF_SOC_MAX = "soc_max"
CONF_EXPENSIVE_THRESHOLD = "expensive_threshold"
CONF_MAX_CHARGE = "max_charge"
CONF_MAX_DISCHARGE = "max_discharge"

# =========================
# Grid Measurement Modes
# =========================

GRID_MODE_SINGLE = "single"   # ein Sensor: +Bezug / -Einspeisung
GRID_MODE_SPLIT = "split"    # zwei Sensoren: Bezug + Einspeisung getrennt

# =========================
# Defaults (nur logisch, NICHT hart verdrahten!)
# =========================

DEFAULT_SOC_MIN = 12
DEFAULT_SOC_MAX = 95
DEFAULT_EXPENSIVE_THRESHOLD = 0.35
DEFAULT_MAX_CHARGE = 2000
DEFAULT_MAX_DISCHARGE = 700

# =========================
# Betriebsmodi (Integration intern)
# =========================

MODE_AUTOMATIC = "automatic"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_MANUAL = "manual"

MODES = [
    MODE_AUTOMATIC,
    MODE_SUMMER,
    MODE_WINTER,
    MODE_MANUAL,
]
