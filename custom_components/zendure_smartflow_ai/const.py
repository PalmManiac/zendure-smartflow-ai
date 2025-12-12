DOMAIN = "zendure_smartflow_ai"

CONF_SOC_SENSOR = "soc_sensor"
CONF_PRICE_SENSOR = "price_sensor"
CONF_MAX_CHARGE = "max_charge_power"
CONF_MAX_DISCHARGE = "max_discharge_power"
CONF_SOC_MIN = "soc_min"
CONF_SOC_MAX = "soc_max"
CONF_EXPENSIVE = "expensive_threshold"
CONF_EXTREME = "extreme_threshold"

DEFAULTS = {
    CONF_SOC_MIN: 12,
    CONF_SOC_MAX: 95,
    CONF_EXPENSIVE: 0.35,
    CONF_EXTREME: 0.49,
    CONF_MAX_CHARGE: 2000,
    CONF_MAX_DISCHARGE: 700,
    "battery_kwh": 5.76,
    "charge_efficiency": 0.75,
    "discharge_efficiency": 0.85,
}
