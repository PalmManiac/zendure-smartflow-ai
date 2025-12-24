from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "zendure_smartflow_ai"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# -------------------------
# Config Flow Keys
# -------------------------
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"

# Optional: Tibber (oder anderer) Export-Sensor mit attributes.data (Liste)
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"

# Zendure / SolarFlow AC Steuer-Entitäten
CONF_AC_MODE_ENTITY = "ac_mode_entity"              # select (input/output/...)
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"      # number (W)
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"    # number (W)

# -------------------------
# Defaults (Integration-Settings)
# -------------------------
UPDATE_INTERVAL = 10  # seconds

DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0  # Herstellerempfehlung ✔

DEFAULT_MAX_CHARGE = 2000.0       # W
DEFAULT_MAX_DISCHARGE = 700.0     # W

DEFAULT_EXPENSIVE_THRESHOLD = 0.35      # €/kWh
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49 # €/kWh (Hard-Peak)

DEFAULT_FREEZE_SECONDS = 120

# -------------------------
# AI / Modes
# -------------------------
AI_MODE_SUMMER = "summer"
AI_MODE_WINTER = "winter"
AI_MODE_MANUAL = "manual"
AI_MODE_OFF = "off"

AI_MODES = [AI_MODE_SUMMER, AI_MODE_WINTER, AI_MODE_MANUAL, AI_MODE_OFF]

MANUAL_ACTION_STANDBY = "standby"
MANUAL_ACTION_CHARGE = "charge"
MANUAL_ACTION_DISCHARGE = "discharge"

MANUAL_ACTIONS = [MANUAL_ACTION_STANDBY, MANUAL_ACTION_CHARGE, MANUAL_ACTION_DISCHARGE]
