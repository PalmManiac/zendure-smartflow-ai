from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

FREEZE_SECONDS = 120  # Recommendation-Freeze


@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str
    price_now: str
    price_export: str

    soc_min: str
    soc_max: str
    expensive_threshold: str
    max_charge: str
    max_discharge: str

    # GUI-Select in deiner Integration (Betriebsmodus)
    ac_mode: str

    # Solarflow-Steuerung (wird hier noch NICHT aktiv genutzt)
    input_limit: str
    output_limit: str


DEFAULT_ENTITY_IDS = EntityIds(
    soc="sensor.solarflow_2400_ac_electric_level",
    pv="sensor.sb2_5_1vl_40_401_pv_power",
    load="sensor.gesamtverbrauch",
    price_now="sensor.paul_schneider_strasse_39_aktueller_strompreis_energie_dashboard",
    price_export="sensor.paul_schneider_strasse_39_diagramm_datenexport",
    soc_min="number.zendure_soc_min",
    soc_max="number.zendure_soc_max",
    expensive_threshold="number.zendure_teuer_schwelle",
    max_charge="number.zendure_max_ladeleistung",
    max_discharge="number.zendure_max_entladeleistung",
    ac_mode="select.zendure_betriebsmodus",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)


def _f(state: Any, default: float = 0.0) -> float:
    try:
        if state is None:
            return default
        return float(str(state).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator: Daten holen + Empfehlung berechnen (V0.1)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        # Entity-IDs (später per ConfigFlow überschreibbar)
        self.entities = DEFAULT_ENTITY_IDS

        # Freeze-Status
        self._last_recommendation: str | None = None
        self._last_ai_status: str | None = None
        self._freeze_until: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    def _state(self, entity_id: str) -> str | None:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    def _prices_future(self) -> list[float]:
        """Tibber Datenexport -> Liste ab JETZT (15min Slots)."""
        export = self._attr(self.entities.price_export, "data")
        if not export:
            return []

        prices = [_f(e.get("price_per_kwh"), 0.0) for e in export]

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        return prices[idx:] if idx < len(prices) else []

    @staticmethod
    def _freeze_active(now_utc: datetime, freeze_until: datetime | None) -> bool:
        return freeze_until is not None and now_utc < freeze_until

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now_utc = dt_util.utcnow()

            # --- Betriebsmodus nur LESEN (niemals setzen!) ---
            mode = self._state(self.entities.ac_mode) or "Automatik"

            soc = _f(self._state(self.entities.soc))
            pv = _f(self._state(self.entities.pv))
            load = _f(self._state(self.entities.load))
            price_now = _f(self._state(self.entities.price_now))

            soc_min = _f(self._state(self.entities.soc_min), 12.0)
            soc_max = _f(self._state(self.entities.soc_max), 95.0)
            expensive_fixed = _f(self._state(self.entities.expensive_threshold), 0.35)

            prices = self._prices_future()

            minp = min(prices) if prices else price_now
            maxp = max(prices) if prices else price_now
            avgp = (sum(prices) / len(prices)) if prices else price_now
            span = maxp - minp
            dynamic_expensive = avgp + span * 0.25
            expensive = max(expensive_fixed, dynamic_expensive)

            surplus = max(pv - load, 0.0)

            # ===== Entscheidung =====
            ai_status = "standby"
            recommendation = "standby"

            soc_notfall = max(soc_min - 4.0, 5.0)

            # 0) Manuell -> nichts automatisch anstoßen
            if str(mode).lower() == "manuell":
                ai_status = "manuell"
                recommendation = "standby"

            # 1) Notfall hat IMMER Vorrang (Freeze aus)
            elif soc <= soc_notfall:
                ai_status = "notladung"
                recommendation = "billig_laden"
                self._freeze_until = None  # Notfall = kein Freeze

            # 2) Teuer jetzt -> entladen wenn möglich, sonst Schutz
            elif price_now >= expensive and soc > soc_min:
                ai_status = "teuer_jetzt"
                recommendation = "entladen"

            # 3) günstigster Slot JETZT -> laden (nur wenn SoC < max)
            elif prices and prices[0] == minp and soc < soc_max:
                ai_status = "günstig_jetzt"
                recommendation = "ki_laden"

            # 4) PV Überschuss -> laden
            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"

            # ===== Recommendation-Freeze (KORREKT) =====
            # Freeze NICHT bei jedem Update neu setzen, sondern nur wenn sich etwas ändert!
            if self._freeze_active(now_utc, self._freeze_until):
                # während Freeze: Werte festhalten
                recommendation = self._last_recommendation or recommendation
                ai_status = self._last_ai_status or ai_status
            else:
                # Freeze ist aus/abgelaufen -> nur neu starten, wenn Wechsel stattfindet
                if recommendation != self._last_recommendation or ai_status != self._last_ai_status:
                    self._freeze_until = now_utc + timedelta(seconds=FREEZE_SECONDS)
                    self._last_recommendation = recommendation
                    self._last_ai_status = ai_status
                # wenn nix wechselt: freeze_until bleibt wie es ist (und ändert keine Attribute)

            # Details (Achtung: keine „zappelnden“ Werte ständig ändern!)
            details = {
                "mode": mode,
                "price_now": round(price_now, 4),
                "min_price": round(minp, 4),
                "max_price": round(maxp, 4),
                "avg_price": round(avgp, 4),
                "expensive_threshold": round(expensive, 4),
                "expensive_fixed": round(expensive_fixed, 4),
                "expensive_dynamic": round(dynamic_expensive, 4),
                "surplus": round(surplus, 1),
                "soc": round(soc, 2),
                "soc_min": round(soc_min, 2),
                "soc_max": round(soc_max, 2),
                "freeze_active": self._freeze_active(now_utc, self._freeze_until),
                "freeze_until": self._freeze_until.isoformat() if self._freeze_until else None,
            }

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": details,
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
