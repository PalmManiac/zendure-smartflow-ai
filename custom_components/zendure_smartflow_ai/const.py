from __future__ import annotations
from homeassistant.const import Platform

DOMAIN = "zendure_smartflow_ai"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# =========================
# Config-Flow Keys
# =========================
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"

CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

# =========================
# Betriebsmodi (Integration)
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

# =========================
# Interne Settings-Keys
# =========================
SETTING_OPERATION_MODE = "operation_mode"

SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_EXPENSIVE_THRESHOLD = "expensive_threshold"
SETTING_PRICE_THRESHOLD = SETTING_EXPENSIVE_THRESHOLD  # Alias!

SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"

# =========================
# Default-Werte
# =========================
DEFAULT_SOC_MIN = 10.0
DEFAULT_SOC_MAX = 100.0
DEFAULT_EXPENSIVE_THRESHOLD = 0.35
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 800.0
