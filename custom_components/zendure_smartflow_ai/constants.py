"""Konstanten für Zendure SmartFlow AI."""

DOMAIN = "zendure_smartflow_ai"

# Betriebsmodi
MODE_AUTOMATIC = "automatic"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_MANUAL = "manual"

ALL_MODES = [
    MODE_AUTOMATIC,
    MODE_SUMMER,
    MODE_WINTER,
    MODE_MANUAL,
]

# Alias für ältere Imports (select.py erwartet MODES)
MODES = ALL_MODES

# Update-Intervall (Sekunden)
DEFAULT_UPDATE_INTERVAL = 10
