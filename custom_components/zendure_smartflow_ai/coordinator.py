from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

FREEZE_SECONDS = 120  # Recommendation-Freeze

# -------------------------------------------------------------

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

    ac_mode: str


DEFAULT_ENTITY_IDS = EntityIds(
    soc="sensor.solarflow_2400_ac_electric_level",
    pv="sensor.sb2_5_1vl_40_401_pv_power",
    load="sensor.gesamtverbrauch",
    price_now="sensor.paul_schneider_strasse_39_aktueller_strompreis_energie_dashboard",
    price_export="sensor.paul_schneider_strasse_39_diagramm_datenexport",
    soc_min="number.zendure_soc_min",
    soc_max="number.zendure_soc_max",
    expensive_threshold="number.zendure_teuer_schwelle",
    ac_mode="select.zendure_betriebsmodus",
)


def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return default


# -------------------------------------------------------------

class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        self.entities = DEFAULT_ENTITY_IDS

        # Freeze-Status
        self._last_recommendation: str | None = None
        self._last_ai_status: str | None = None
        self._freeze_until = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    # ---------------------------------------------------------

    def _state(self, entity_id: str) -> str | None:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # ---------------------------------------------------------

    def _prices_future(self) -> list[float]:
        export = self._attr(self.entities.price_export, "data")
        if not export:
            return []

        prices = [_f(e.get("price_per_kwh"), 0.0) for e in export]
        now = dt_util.now()
        idx = (now.hour * 60 + now.minute) // 15
        return prices[idx:]

    # ---------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            soc = _f(self._state(self.entities.soc))
            pv = _f(self._state(self.entities.pv))
            load = _f(self._state(self.entities.load))
            price_now = _f(self._state(self.entities.price_now))

            soc_min = _f(self._state(self.entities.soc_min), 12)
            soc_max = _f(self._state(self.entities.soc_max), 95)
            soc_notfall = max(soc_min - 4, 5)

            expensive_fixed = _f(self._state(self.entities.expensive_threshold), 0.35)

            mode = (self._state(self.entities.ac_mode) or "Automatik").lower()

            prices = self._prices_future()
            minp = min(prices) if prices else price_now
            maxp = max(prices) if prices else price_now
            avgp = sum(prices) / len(prices) if prices else price_now
            span = maxp - minp

            expensive = max(expensive_fixed, avgp + span * 0.25)
            surplus = max(pv - load, 0)

            # -------------------------------------------------
            # Default
            ai_status = "standby"
            recommendation = "standby"

            # -------------------------------------------------
            # Betriebsmodi
            if mode == "manuell":
                ai_status = "manuell"
                recommendation = "standby"
                self._freeze_until = None

            elif mode == "sommer":
                if soc <= soc_notfall:
                    ai_status = "notladung"
                    recommendation = "billig_laden"
                    self._freeze_until = None
                elif surplus > 80 and soc < soc_max:
                    ai_status = "pv_laden"
                    recommendation = "laden"
                else:
                    ai_status = "standby"
                    recommendation = "standby"
                self._freeze_until = None

            else:
                # Automatik + Winter
                if soc <= soc_notfall:
                    ai_status = "notladung"
                    recommendation = "billig_laden"
                    self._freeze_until = None

                elif price_now >= expensive and soc > soc_min:
                    ai_status = "teuer_jetzt"
                    recommendation = "entladen"

                elif prices and prices[0] == minp and soc < soc_max:
                    ai_status = "günstig_jetzt"
                    recommendation = "ki_laden"

                elif surplus > 80 and soc < soc_max:
                    ai_status = "pv_laden"
                    recommendation = "laden"

                # Freeze
                if self._freeze_until and now < self._freeze_until:
                    recommendation = self._last_recommendation
                    ai_status = self._last_ai_status
                else:
                    self._last_recommendation = recommendation
                    self._last_ai_status = ai_status
                    self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)

            # -------------------------------------------------

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "mode": mode,
                    "soc": soc,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "price_now": price_now,
                    "min_price": minp,
                    "max_price": maxp,
                    "avg_price": avgp,
                    "expensive_threshold": expensive,
                    "surplus": surplus,
                    "freeze_until": self._freeze_until.isoformat() if self._freeze_until else None,
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
