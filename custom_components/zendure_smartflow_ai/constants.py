DOMAIN = "zendure_smartflow_ai"

PLATFORMS = ["sensor", "select", "number"]

# Betriebsmodi (intern)
MODE_AUTOMATIC = "automatic"
MODE_SUMMER = "summer"
MODE_WINTER = "winter"
MODE_MANUAL = "manual"

# Anzeige-Optionen im Select
MODES = {
    MODE_AUTOMATIC: "Automatik",
    MODE_SUMMER: "Sommer",
    MODE_WINTER: "Winter",
    MODE_MANUAL: "Manuell",
}

DEFAULT_MODE = MODE_AUTOMATIC

DEFAULT_SOC_MIN = 12.0
DEFAULT_SOC_MAX = 100.0
