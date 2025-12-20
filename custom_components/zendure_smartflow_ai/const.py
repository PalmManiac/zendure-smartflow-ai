from __future__ import annotations

from homeassistant.const import Platform

# =====================================================
# Domain
# =====================================================
DOMAIN = "zendure_smartflow_ai"

# =====================================================
# Platforms
# =====================================================
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

# =====================================================
# Config Flow Keys (Benutzer-Auswahl)
# =====================================================

# Messwerte
CONF_SOC_ENTITY = "soc_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_LOAD_ENTITY = "load_entity"

# Preise
CONF_PRICE_NOW_ENTITY = "price_now_entity"
CONF_PRICE_EXPORT_ENTITY = "price_export_entity"

# Zendure Steuerung
CONF_AC_MODE_ENTITY = "ac_mode_entity"
CONF_INPUT_LIMIT_ENTITY = "input_limit_entity"
CONF_OUTPUT_LIMIT_ENTITY = "output_limit_entity"

# Grid / Netz
CONF_GRID_MODE = "grid_mode"
CONF_GRID_POWER_ENTITY = "grid_power_entity"
CONF_GRID_IMPORT_ENTITY = "grid_import_entity"
CONF_GRID_EXPORT_ENTITY = "grid_export_entity"

# =====================================================
# Grid Modes
# =====================================================
GRID_MODE_SINGLE = "single"
GRID_MODE_SPLIT = "split"

# =====================================================
# Interne SETTINGS
# (werden von number.py / select.py genutzt)
# =====================================================

SETTING_SOC_MIN = "soc_min"
SETTING_SOC_MAX = "soc_max"

SETTING_EXPENSIVE_THRESHOLD = "expensive_threshold"

# ⚠️ Diese Namen sind absichtlich so gewählt,
# damit number.py NICHT geändert werden muss
SETTING_MAX_CHARGE = "max_charge"
SETTING_MAX_DISCHARGE = "max_discharge"

SETTING_OPERATION_MODE = "operation_mode"  # auto / summer / winter / manual
