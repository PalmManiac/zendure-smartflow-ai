from __future__ import annotations

from typing import Any, Dict, List
from statistics import mean


def calculate_ai_state(
    *,
    prices: List[float],
    current_price: float,
    soc: float,
    soc_min: float,
    soc_max: float,
    soc_emergency: float,
    usable_kwh: float,
    max_charge_w: float,
    max_discharge_w: float,
    expensive_threshold: float,
) -> Dict[str, Any]:
    """
    Zentrale KI-Entscheidungslogik für Zendure SmartFlow AI.

    Liefert:
      - ai_status        (interner KI-Zustand, technisch)
      - recommendation  (für Steuerung / Automationen)
      - debug            (kurzer Text, state-tauglich)
      - details          (strukturierte Debug-Daten als Attribute)
    """

    result: Dict[str, Any] = {
        "ai_status": "idle",
        "recommendation": "idle",
        "debug": "OK",
        "details": {},
        "price_now": current_price,
        "expensive_threshold": expensive_threshold,
    }

    # ------------------------------------------------------------------
    # 0) Grundprüfungen
    # ------------------------------------------------------------------
    if not prices or len(prices) < 2:
        result["ai_status"] = "no_price_data"
        result["recommendation"] = "idle"
        result["debug"] = "NO_PRICE_DATA"
        return result

    future_prices = prices[:]  # ab jetzt
    min_price = min(future_prices)
    max_price = max(future_prices)
    avg_price = mean(future_prices)

    # ------------------------------------------------------------------
    # 1) Notfall: Akku schützen (höchste Priorität)
    # ------------------------------------------------------------------
    if soc <= soc_emergency:
        result["ai_status"] = "emergency"
        result["recommendation"] = "emergency_charge"
        result["debug"] = "EMERGENCY_CHARGE"
        result["details"] = {
            "reason": "soc_emergency",
            "soc": soc,
        }
        return result

    # ------------------------------------------------------------------
    # 2) Peak-Analyse (intern, nicht als State!)
    # ------------------------------------------------------------------
    peak_slots = [p for p in future_prices if p >= expensive_threshold]
    peak_hours = len(peak_slots) * 0.25

    discharge_kw = max_discharge_w / 1000.0 if max_discharge_w > 0 else 0
    charge_kw = max_charge_w / 1000.0 if max_charge_w > 0 else 0

    needed_kwh = peak_hours * discharge_kw
    missing_kwh = max(needed_kwh - usable_kwh, 0)

    # erster Peak-Index
    first_peak_idx = None
    for i, p in enumerate(future_prices):
        if p >= expensive_threshold:
            first_peak_idx = i
            break

    minutes_to_peak = first_peak_idx * 15 if first_peak_idx is not None else None

    if charge_kw > 0:
        need_minutes = (missing_kwh / charge_kw) * 60 if missing_kwh > 0 else 0
    else:
        need_minutes = 0

    safety_margin = 30  # Minuten

    # ------------------------------------------------------------------
    # 3) ZWANGSLADEN: Laden muss JETZT beginnen
    # ------------------------------------------------------------------
    if (
        first_peak_idx is not None
        and missing_kwh > 0
        and minutes_to_peak is not None
        and minutes_to_peak <= (need_minutes + safety_margin)
        and soc < soc_max
    ):
        result["ai_status"] = "charge_required"
        result["recommendation"] = "charge_now"
        result["debug"] = "CHARGE_NOW_FOR_PEAK"
        result["details"] = {
            "missing_kwh": round(missing_kwh, 2),
            "minutes_to_peak": minutes_to_peak,
            "need_minutes": round(need_minutes, 1),
        }
        return result

    # ------------------------------------------------------------------
    # 4) PV-Überschuss (wird außerhalb bewertet, hier nur freigeben)
    # ------------------------------------------------------------------
    # → recommendation pv_charge wird im Coordinator gesetzt,
    #   wenn Überschuss gemeldet wird

    # ------------------------------------------------------------------
    # 5) Teure Phase → Entladen sinnvoll
    # ------------------------------------------------------------------
    if current_price >= expensive_threshold and soc > (soc_min + 2):
        result["ai_status"] = "expensive_now"
        result["recommendation"] = "discharge"
        result["debug"] = "DISCHARGE_RECOMMENDED"
        result["details"] = {
            "current_price": current_price,
            "threshold": expensive_threshold,
        }
        return result

    # ------------------------------------------------------------------
    # 6) Warten auf günstigste Phase
    # ------------------------------------------------------------------
    cheapest_idx = future_prices.index(min_price)
    cheapest_future = cheapest_idx > 0

    if cheapest_future and soc < soc_max:
        result["ai_status"] = "waiting_cheapest"
        result["recommendation"] = "wait_for_cheapest"
        result["debug"] = "WAIT_FOR_CHEAPEST"
        result["details"] = {
            "cheapest_price": min_price,
            "minutes_to_cheapest": cheapest_idx * 15,
        }
        return result

    # ------------------------------------------------------------------
    # 7) Default
    # ------------------------------------------------------------------
    result["ai_status"] = "idle"
    result["recommendation"] = "idle"
    result["debug"] = "IDLE"
    result["details"] = {
        "min_price": min_price,
        "max_price": max_price,
        "avg_price": round(avg_price, 4),
        "missing_kwh": round(missing_kwh, 2),
    }

    return result
