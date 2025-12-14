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

FREEZE_SECONDS = 900  # 15 Minuten


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

    ac_mode: str
    input_limit: str
    output_limit: str


DEFAULT_ENTITY_IDS = EntityIds(
    soc="sensor.solarflow_2400_ac_electric_level",
    pv="sensor.sb2_5_1vl_40_401_pv_power",
    load="sensor.gesamtverbrauch",
    price_now="sensor.paul_schneider_strasse_39_aktueller_strompreis_energie_dashboard",
    price_export="sensor.paul_schneider_strasse_39_diagramm_datenexport",
    soc_min="input_number.zendure_soc_reserve_min",
    soc_max="input_number.zendure_soc_ziel_max",
    expensive_threshold="input_number.zendure_schwelle_teuer",
    max_charge="input_number.zendure_max_ladeleistung",
    max_discharge="input_number.zendure_max_entladeleistung",
    ac_mode="select.solarflow_2400_ac_ac_mode",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)


def _f(state: str | None, default: float = 0.0) -> float:
    try:
        return float(str(state).replace(",", ".")) if state is not None else default
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        self.entities = DEFAULT_ENTITY_IDS

        self._last_recommendation: str | None = None
        self._last_recommendation_ts: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    def _state(self, eid: str) -> str | None:
        st = self.hass.states.get(eid)
        return None if st is None else st.state

    def _attr(self, eid: str, attr: str) -> Any:
        st = self.hass.states.get(eid)
        return None if st is None else st.attributes.get(attr)

    def _prices(self) -> list[float]:
        export = self._attr(self.entities.price_export, "data")
        if not export:
            return []
        return [_f(i.get("price_per_kwh"), 0.0) for i in export]

    def _idx_now(self) -> int:
        now = dt_util.now()
        return (now.hour * 60 + now.minute) // 15

    def _allow_change(self, new: str, force: bool) -> bool:
        if force:
            return True
        if self._last_recommendation is None:
            return True
        if new != self._last_recommendation:
            if self._last_recommendation_ts is None:
                return True
            age = dt_util.utcnow().timestamp() - self._last_recommendation_ts
            return age >= FREEZE_SECONDS
        return False

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc = _f(self._state(self.entities.soc))
            pv = _f(self._state(self.entities.pv))
            load = _f(self._state(self.entities.load))
            price_now = _f(self._state(self.entities.price_now))

            soc_min = _f(self._state(self.entities.soc_min), 12)
            soc_max = _f(self._state(self.entities.soc_max), 95)
            soc_notfall = max(soc_min - 4, 5)

            expensive_fixed = _f(self._state(self.entities.expensive_threshold), 0.35)

            prices = self._prices()
            idx = self._idx_now()
            future = prices[idx:] if idx < len(prices) else []

            if future:
                minp = min(future)
                maxp = max(future)
                avg = sum(future) / len(future)
                span = maxp - minp
                expensive = max(expensive_fixed, avg + span * 0.25)
            else:
                minp = maxp = avg = price_now
                expensive = expensive_fixed

            ai_status = "standby"
            recommendation = "standby"
            force_change = False

            if soc <= soc_notfall:
                ai_status = "notladung"
                recommendation = "billig_laden"
                force_change = True

            elif price_now >= expensive:
                if soc <= soc_min:
                    ai_status = "teuer_akkuschutz"
                    recommendation = "standby"
                else:
                    ai_status = "teuer_entladen"
                    recommendation = "entladen"
                force_change = True

            elif future and future[0] == min(future) and soc < soc_max:
                ai_status = "günstig_jetzt"
                recommendation = "ki_laden"

            elif pv - load > 80 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"

            if not self._allow_change(recommendation, force_change):
                recommendation = self._last_recommendation or recommendation

            if recommendation != self._last_recommendation:
                self._last_recommendation = recommendation
                self._last_recommendation_ts = dt_util.utcnow().timestamp()

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "price_now": price_now,
                    "min_price": minp,
                    "max_price": maxp,
                    "avg_price": avg,
                    "expensive": expensive,
                    "soc": soc,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "freeze_seconds": FREEZE_SECONDS,
                },
            }

        except Exception as err:
            raise UpdateFailed(err)
