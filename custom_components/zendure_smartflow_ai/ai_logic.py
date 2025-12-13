from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from .const import (
    AI_STATUS_NO_DATA,
    AI_STATUS_EXPENSIVE_NOW_PROTECT,
    AI_STATUS_EXPENSIVE_NOW_DISCHARGE,
    AI_STATUS_CHARGE_FOR_PEAK,
    AI_STATUS_WAIT_FOR_CHEAPEST,
    AI_STATUS_IDLE,
    RECOMMENDATION_STANDBY,
    RECOMMENDATION_CHARGE,
    RECOMMENDATION_DISCHARGE,
    RECOMMENDATION_KI_CHARGE,
)


def calculate_ai_state(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Zentrale KI-Logik für Zendure SmartFlow AI

    Erwartete Keys in `data`:
    - soc (float, %)
    - soc_min (float)
    - soc_max (float)
    - prices (list[float])  # 15-Minuten-Preise, ab JETZT
    - current_price (float)
    - expensive_threshold (float)
    - cheap_threshold (float)
    - battery_kwh (float)
    - max_charge_w (float)
    - max_discharge_w (float)

    Rückgabe:
    {
        "ai_status": <ENUM>,
        "recommendation": <ENUM>,
        "debug": str
    }
    """

    # -----------------------------
    # 1. Basiswerte einlesen
    # -----------------------------
    soc: float = float(data.get("soc", 0))
    soc_min: float = float(data.get("soc_min", 12))
    soc_max: float = float(data.get("soc_max", 95))

    prices = data.get("prices", [])
    current_price: float = float(data.get("current_price", 0))

    expensive = float(data.get("expensive_threshold", 0.35))
    cheap = float(data.get("cheap_threshold", 0.15))

    battery_kwh: float = float(data.get("battery_kwh", 5.76))
    max_charge_w: float = float(data.get("max_charge_w", 2000))
    max_discharge_w: float = float(data.get("max_discharge_w", 700))

    now = datetime.now()

    # -----------------------------
    # 2. Validierung
    # -----------------------------
    if not prices:
        return {
            "ai_status": AI_STATUS_NO_DATA,
            "recommendation": RECOMMENDATION_STANDBY,
            "debug": "Keine Preisdaten vorhanden"
        }

    # -----------------------------
    # 3. Energie-Berechnungen
    # -----------------------------
    usable_soc = max(soc - soc_min, 0)
    available_kwh = battery_kwh * usable_soc / 100

    charge_kw = (max_charge_w * 0.75) / 1000
    discharge_kw = (max_discharge_w * 0.85) / 1000

    # -----------------------------
    # 4. Peak-Erkennung
    # -----------------------------
    peak_slots = [p for p in prices if p >= expensive]
    peak_hours = len(peak_slots) * 0.25
    needed_kwh = peak_hours * discharge_kw
    missing_kwh = max(needed_kwh - available_kwh, 0)

    # ersten Peak in der Zukunft finden
    first_peak_index = None
    for i, p in enumerate(prices):
        if p >= expensive:
            first_peak_index = i
            break

    minutes_to_peak = first_peak_index * 15 if first_peak_index is not None else None
    needed_minutes = (missing_kwh / charge_kw * 60) if charge_kw > 0 else 0

    # günstigster Slot
    cheapest_price = min(prices)
    cheapest_index = prices.index(cheapest_price)
    cheapest_in_future = cheapest_index > 0

    # -----------------------------
    # 5. Entscheidungslogik
    # -----------------------------

    # A) Aktuell teuer
    if current_price >= expensive:
        if soc <= soc_min:
            return {
                "ai_status": AI_STATUS_EXPENSIVE_NOW_PROTECT,
                "recommendation": RECOMMENDATION_STANDBY,
                "debug": "Teurer Preis, Akku unter Reserve → Schutz"
            }
        else:
            return {
                "ai_status": AI_STATUS_EXPENSIVE_NOW_DISCHARGE,
                "recommendation": RECOMMENDATION_DISCHARGE,
                "debug": "Teurer Preis, Akku ausreichend → Entladen empfohlen"
            }

    # B) Peak kommt & Energie fehlt → gezielt laden
    if (
        first_peak_index is not None
        and missing_kwh > 0
        and minutes_to_peak is not None
        and minutes_to_peak <= needed_minutes + 30
        and soc < soc_max
    ):
        return {
            "ai_status": AI_STATUS_CHARGE_FOR_PEAK,
            "recommendation": RECOMMENDATION_KI_CHARGE,
            "debug": (
                f"Peak in {minutes_to_peak} min, "
                f"fehlend {missing_kwh:.2f} kWh → Laden erforderlich"
            )
        }

    # C) Günstigste Phase kommt noch → warten
    if cheapest_in_future and soc < soc_max:
        return {
            "ai_status": AI_STATUS_WAIT_FOR_CHEAPEST,
            "recommendation": RECOMMENDATION_STANDBY,
            "debug": (
                f"Günstigster Preis ({cheapest_price:.3f} €/kWh) "
                f"in {cheapest_index * 15} min"
            )
        }

    # D) Nichts Besonderes
    return {
        "ai_status": AI_STATUS_IDLE,
        "recommendation": RECOMMENDATION_STANDBY,
        "debug": "Keine besondere Aktion erforderlich"
    }
