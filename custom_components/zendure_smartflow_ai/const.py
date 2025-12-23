from __future__ import annotations
from homeassistant.const import Platform

DOMAIN = "zendure_smartflow_ai"

PLATFORMS = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# -----------------
# Config Flow Keys
# -----------------
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"

CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

# -----------------
# Defaults
# -----------------
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0
DEFAULT_EXPENSIVE_THRESHOLD = 0.35

UPDATE_INTERVAL = 10
