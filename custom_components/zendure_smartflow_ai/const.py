DOMAIN = "zendure_smartflow_ai"

# Sensor-Namen
SENSOR_KI_STATUS = "zendure_smartflow_ai_ki_ladeplan"

# Defaults (werden später GUI-konfigurierbar)
DEFAULTS = {
    "battery_kwh": 5.76,
    "charge_efficiency": 0.75,
    "discharge_efficiency": 0.85,
    "min_peak_duration_h": 0.5,
    "horizon_slots": 96,  # 24h bei 15-Minuten
}
