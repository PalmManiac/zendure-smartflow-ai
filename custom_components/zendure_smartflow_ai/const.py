from __future__ import annotations

from homeassistant.const import Platform

# =========================
# Domain & Version
# =========================
DOMAIN = "zendure_smartflow_ai"
VERSION = "0.1.1"

# =========================
# Platforms
# =========================
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# =========================
# Config Keys (Config Flow)
# =========================

# Basis-Sensoren
CONF_SOC_ENTITY = "soc_entity"              # Batterie SoC (%)
CONF_PV_ENTITY = "pv_entity"                # PV-Leistung (W)
CONF_LOAD_ENTITY = "load_entity"            # Hausverbrauch (W)

# Strompreise
CONF_PRICE_NOW_ENTITY = "price_now_entity"          # aktueller Preis (€/kWh)
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"    # Tibber / Datenexport (Attribut: data)

# Zendure Steuerung
CONF_AC_MODE_ENTITY = "ac_mode_entity"              # select.xxx (input/output)
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"      # number.xxx
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"    # number.xxx

# =========================
# Grid / Netzanschluss
# =========================

CONF_GRID_MODE = "grid_mode"

# ein Sensor (+ Bezug / – Einspeisung)
CONF_GRID_POWER_ENTITY = "grid_power_entity"

# getrennte Sensoren
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

# =========================
# Grid Modes
# =========================
GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# =========================
# Defaults / Intern
# =========================
DEFAULT_UPDATE_INTERVAL = 10       # Sekunden
DEFAULT_FREEZE_SECONDS = 120       # Recommendation-Freeze
