from __future__ import annotations


def calculate_ai_state(
    prices: list[float],
    soc: float,
    soc_min: float,
    soc_max: float,
    battery_kwh: float,
    max_charge_w: float,
    max_discharge_w: float,
    expensive_threshold: float,
) -> dict:
    """
    Zentrale KI-Logik für Zendure SmartFlow AI.
    Gibt ausschließlich strukturierte Zustände zurück (keine HA-Abhängigkeiten).
    """

    # ---------- Defaults ----------
    result = {
        "ai_status": "no_data",
        "ai_status_text": "Keine Preisdaten verfügbar",
        "recommendation": "standby",
        "recommendation_reason": "Preis- oder Systemdaten fehlen",
        "debug": {},
        "debug_short": "no_prices",
    }

    if not prices:
        return result

    # ---------- Grundwerte ----------
    current_price = prices[0]
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)
    span = max_price - min_price

    usable_kwh = battery_kwh * max(soc - soc_min, 0) / 100
    charge_kw = (max_charge_w * 0.75) / 1000
    discharge_kw = (max_discharge_w * 0.85) / 1000

    # Dynamische Schwelle
    dynamic_expensive = avg_price + span * 0.25
    expensive = max(expensive_threshold, dynamic_expensive)

    # Peak-Erkennung
    peak_slots = [p for p in prices if p >= expensive]
    peak_hours = len(peak_slots) * 0.25
    needed_kwh = peak_hours * discharge_kw
    missing_kwh = max(needed_kwh - usable_kwh, 0)

    # Indexe
    first_peak_index = None
    for i, p in enumerate(prices):
        if p >= expensive:
            first_peak_index = i
            break

    cheapest_price = min_price
    cheapest_index = prices.index(cheapest_price)

    # ---------- Statuslogik ----------
    if current_price >= expensive:
        if soc <= soc_min:
            result.update(
                ai_status="teuer_jetzt_akkuschutz",
                ai_status_text="Hoher Preis – Akku zu leer zum Entladen",
                recommendation="standby",
                recommendation_reason="Akkuschutz bei hoher Preisphase",
                debug_short="expensive_now_protect",
            )
        else:
            result.update(
                ai_status="teuer_jetzt_entladen",
                ai_status_text="Hoher Preis – Entladen empfohlen",
                recommendation="entladen",
                recommendation_reason="Netzpreis hoch, Akku hat Reserve",
                debug_short="expensive_now_discharge",
            )

    elif missing_kwh > 0 and first_peak_index is not None:
        minutes_to_peak = first_peak_index * 15
        needed_minutes = (missing_kwh / charge_kw * 60) if charge_kw > 0 else 0

        if minutes_to_peak <= needed_minutes + 30:
            result.update(
                ai_status="laden_notwendig_fuer_peak",
                ai_status_text="Energie reicht nicht für kommende Peakphase",
                recommendation="ki_laden",
                recommendation_reason="Vorbereitung auf hohe Preisphase",
                debug_short="charge_for_peak",
            )
        else:
            result.update(
                ai_status="peak_spaeter",
                ai_status_text="Peak erkannt – Laden später ausreichend",
                recommendation="standby",
                recommendation_reason="Noch ausreichend Zeit bis Peak",
                debug_short="wait_for_peak",
            )

    elif cheapest_index > 0 and soc < soc_max:
        result.update(
            ai_status="guenstige_phase_kommt",
            ai_status_text="Günstigste Preisphase kommt noch",
            recommendation="standby",
            recommendation_reason="Warten auf günstigeres Zeitfenster",
            debug_short="cheapest_future",
        )

    else:
        result.update(
            ai_status="ausreichend_geladen",
            ai_status_text="Keine Aktion erforderlich",
            recommendation="standby",
            recommendation_reason="Kein wirtschaftlicher Vorteil erkennbar",
            debug_short="idle",
        )

    # ---------- Debug ----------
    result["debug"] = {
        "current_price": round(current_price, 4),
        "min_price": round(min_price, 4),
        "max_price": round(max_price, 4),
        "avg_price": round(avg_price, 4),
        "expensive_threshold": round(expensive, 4),
        "usable_kwh": round(usable_kwh, 2),
        "needed_kwh": round(needed_kwh, 2),
        "missing_kwh": round(missing_kwh, 2),
        "first_peak_index": first_peak_index,
        "cheapest_index": cheapest_index,
    }

    return result
