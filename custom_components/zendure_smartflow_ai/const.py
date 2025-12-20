from __future__ import annotations

from homeassistant.const import Platform

# =========================
# Domain
# =========================
DOMAIN = "zendure_smartflow_ai"

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

# --- Messwerte ---
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"

# --- Strompreise ---
CONF_PRICE_NOW_ENTITY = "price_now_entity"
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"

# --- Zendure Steuerung (SolarFlow AC) ---
CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

# --- Netz / Grid Logik (V0.2.x) ---
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

# =========================
# Grid Modes
# =========================
GRID_MODE_SINGLE = "single"   # ein Sensor (+Bezug / −Einspeisung)
GRID_MODE_SPLIT = "split"    # getrennte Sensoren
