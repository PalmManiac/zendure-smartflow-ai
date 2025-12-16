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

FREEZE_SECONDS = 120  # Recommendation-Freeze (2 Minuten)


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
    soc_min="number.zendure_soc_min",
    soc_max="number.zendure_soc_max",
    expensive_threshold="number.zendure_teuer_schwelle",
    max_charge="number.zendure_max_ladeleistung",
    max_discharge="number.zendure_max_entladeleistung",
    ac_mode="select.solarflow_2400_ac_ac_mode",
    input_limit="number.solarflow_2400_ac_input_limit",
    output_limit="number.solarflow_2400_ac_output_limit",
)


def _f(state: str | None, default: float = 0.0) -> float:
    try:
        if state in (None, "unknown", "unavailable"):
            return default
        return float(str(state).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Zentrale KI-Logik + direkte Akku-Steuerung"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id
        self.entities = DEFAULT_ENTITY_IDS

        # Recommendation-Freeze
        self._last_recommendation: str | None = None
        self._last_ai_status: str | None = None
        self._freeze_until = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    # ---------------------------------------------------------------------

    def _state(self, entity: str) -> str | None:
        s = self.hass.states.get(entity)
        return None if s is None else s.state

    def _attr(self, entity: str, attr: str) -> Any:
        s = self.hass.states.get(entity)
        return None if s is None else s.attributes.get(attr)

    def _prices_future(self) -> list[float]:
        export = self._attr(self.entities.price_export, "data")
        if not export:
            return []

        prices = [_f(e.get("price_per_kwh"), 0.0) for e in export]

        now = dt_util.now()
        idx = (now.hour * 60 + now.minute) // 15
        return prices[idx:]

    # ---------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            # ===== Basiswerte =====
            soc_raw = self._state(self.entities.soc)
            if soc_raw in (None, "unknown", "unavailable"):
                raise UpdateFailed("SoC invalid")

            soc = _f(soc_raw)
            pv = _f(self._state(self.entities.pv))
            load = _f(self._state(self.entities.load))
            price_now = _f(self._state(self.entities.price_now))

            soc_min = _f(self._state(self.entities.soc_min), 12.0)
            soc_max = _f(self._state(self.entities.soc_max), 95.0)
            expensive_fixed = _f(self._state(self.entities.expensive_threshold), 0.35)

            max_charge = _f(self._state(self.entities.max_charge), 2000.0)
            max_discharge = _f(self._state(self.entities.max_discharge), 700.0)

            prices = self._prices_future()

            # ===== Preisstatistik =====
            if prices:
                minp = min(prices)
                maxp = max(prices)
                avgp = sum(prices) / len(prices)
                span = maxp - minp
                expensive = max(expensive_fixed, avgp + span * 0.25)
            else:
                minp = maxp = avgp = price_now
                expensive = expensive_fixed

            surplus = max(pv - load, 0.0)

            # ===== Notfallgrenze (HART abgesichert!) =====
            soc_notfall = max(soc_min - 4.0, 5.0)

            # ===== Entscheidung =====
            ai_status = "standby"
            recommendation = "standby"
            control_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # 1) NOTLADUNG – nur wirklich tief!
            if soc <= soc_notfall and soc < soc_min and soc < 20:
                ai_status = "notladung"
                recommendation = "billig_laden"
                control_mode = "input"
                in_w = min(max_charge, 300.0)
                out_w = 0.0
                self._freeze_until = None  # Notfall bricht Freeze

            # 2) TEURER STROM → ENTLADELOGIK
            elif price_now >= expensive and soc > soc_min:
                ai_status = "teuer_jetzt"
                recommendation = "entladen"
                control_mode = "output"
                need = max(load - pv, 0.0)
                out_w = min(max_discharge, need)
                in_w = 0.0

            # 3) GÜNSTIGSTE PHASE → LADEN
            elif prices and prices[0] == minp and soc < soc_max:
                ai_status = "günstig_jetzt"
                recommendation = "ki_laden"
                control_mode = "input"
                in_w = max_charge
                out_w = 0.0

            # 4) PV-ÜBERSCHUSS
            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                control_mode = "input"
                in_w = min(max_charge, surplus)
                out_w = 0.0

            # 5) STANDBY
            else:
                ai_status = "standby"
                recommendation = "standby"
                control_mode = "input"
                in_w = 0.0
                out_w = 0.0

            # ===== Recommendation-Freeze =====
            if self._freeze_until and now < self._freeze_until:
                recommendation = self._last_recommendation
                ai_status = self._last_ai_status
            else:
                self._last_recommendation = recommendation
                self._last_ai_status = ai_status
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)

            # ===== Hardware-Steuerung =====
            await self.hass.services.async_call(
                "select",
                "select_option",
                {
                    "entity_id": self.entities.ac_mode,
                    "option": control_mode,
                },
                blocking=False,
            )

            await self.hass.services.async_call(
                "number",
                "set_value",
                {
                    "entity_id": self.entities.input_limit,
                    "value": round(in_w, 0),
                },
                blocking=False,
            )

            await self.hass.services.async_call(
                "number",
                "set_value",
                {
                    "entity_id": self.entities.output_limit,
                    "value": round(out_w, 0),
                },
                blocking=False,
            )

            # ===== Rückgabe =====
            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
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
                    "set_mode": control_mode,
                    "set_input_w": in_w,
                    "set_output_w": out_w,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
