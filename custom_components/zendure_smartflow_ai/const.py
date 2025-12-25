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
# Update / Polling
# ==================================================
UPDATE_INTERVAL = 10  # seconds

# ==================================================
# Config Flow – Entity Auswahl (Input-Sensoren / Zendure-Steuerung)
# ==================================================
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"

# Preis: optional, weil es auch PV-only Nutzer gibt
CONF_PRICE_NOW_ENTITY = "price_now_entity"          # optional (direkter Preis-Sensor)
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"    # optional (z.B. Tibber Datenexport)

# Zendure / SolarFlow AC Steuer-Entitäten
CONF_AC_MODE_ENTITY = "ac_mode_entity"              # select.* (input/output)
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"      # number.* (W)
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"    # number.* (W)

# ==================================================
# Grid / Hausanschluss (optional, ggf. erst später genutzt)
# ==================================================
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"        # +Bezug / -Einspeisung
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"      # Bezug separat
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"      # Einspeisung separat

GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# ==================================================
# Integration Settings (Number-Entities die Integration bereitstellt)
# (Diese Keys nutzt number.py intern als „setting id“)
# ==================================================
SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"
SETTING_PRICE_THRESHOLD = "price_threshold"
SETTING_VERY_EXPENSIVE_THRESHOLD = "very_expensive_threshold"  # optional / später nutzbar

# ==================================================
# Defaults (sinnvolle Startwerte)
# ==================================================
DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0  # Hersteller-/Anwenderempfehlung (wie von dir gemerkt)
DEFAULT_MAX_CHARGE = 2000.0
DEFAULT_MAX_DISCHARGE = 700.0

DEFAULT_EXPENSIVE_THRESHOLD = 0.35
DEFAULT_VERY_EXPENSIVE_THRESHOLD = 0.49

# ==================================================
# Select: AI Betriebsmodus (Integration-Select)
# Werte sind intern stabil, Übersetzung kommt über strings/de.json
# ==================================================
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
# Select: Manuelle Aktion (Integration-Select)
# ==================================================
MANUAL_ACTION_STANDBY = "standby"
MANUAL_ACTION_CHARGE = "charge"
MANUAL_ACTION_DISCHARGE = "discharge"

MANUAL_ACTIONS = [
    MANUAL_ACTION_STANDBY,
    MANUAL_ACTION_CHARGE,
    MANUAL_ACTION_DISCHARGE,
]

# ==================================================
# Backward compatibility / Aliase (wichtig!)
# Damit alte Imports NICHT brechen, wenn irgendwo noch alte Namen stehen.
# ==================================================
# Manche Versionen hatten "DEFAULT_PRICE_THRESHOLD" statt "DEFAULT_EXPENSIVE_THRESHOLD"
DEFAULT_PRICE_THRESHOLD = DEFAULT_EXPENSIVE_THRESHOLD

# Manche Versionen hatten mal "DEFAULT_EXPENSIVE" / "DEFAULT_EXPENSIVE_THRESHOLD"
DEFAULT_EXPENSIVE = DEFAULT_EXPENSIVE_THRESHOLD
