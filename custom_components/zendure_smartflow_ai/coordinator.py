from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .constants import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _f(val, default=0.0) -> float:
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Zentrale KI-Logik + direkte Akku-Steuerung"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        self._last_recommendation: str | None = None
        self._freeze_until: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    # ---------------------------------------------------------------------
    # Helfer
    # ---------------------------------------------------------------------

    def _state(self, entity_id: str) -> str | None:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    def _now_ts(self) -> float:
        return dt_util.now().timestamp()

    # ---------------------------------------------------------------------
    # Zendure Steuerung (NUR Gerät, KEINE UI-Selects!)
    # ---------------------------------------------------------------------

    async def _set_ac_mode(self, mode: str) -> None:
        await self.hass.services.async_call(
            "select",
            "select_option",
            {
                "entity_id": "select.solarflow_2400_ac_ac_mode",
                "option": mode,
            },
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {
                "entity_id": "number.solarflow_2400_ac_input_limit",
                "value": round(watts, 0),
            },
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {
                "entity_id": "number.solarflow_2400_ac_output_limit",
                "value": round(watts, 0),
            },
            blocking=False,
        )

    # ---------------------------------------------------------------------
    # Hauptlogik
    # ---------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # ---------------- Basiswerte ----------------
            soc = _f(self._state("sensor.solarflow_2400_ac_electric_level"))
            pv = _f(self._state("sensor.sb2_5_1vl_40_401_pv_power"))
            load = _f(self._state("sensor.gesamtverbrauch"))
            price_now = _f(self._state("sensor.paul_schneider_strasse_39_aktueller_strompreis_energie_dashboard"))

            soc_min = _f(self._state("input_number.zendure_soc_reserve_min"), 12)
            soc_max = _f(self._state("input_number.zendure_soc_ziel_max"), 95)
            expensive_fixed = _f(self._state("input_number.zendure_schwelle_teuer"), 0.35)

            max_charge = _f(self._state("input_number.zendure_max_ladeleistung"), 2000)
            max_discharge = _f(self._state("input_number.zendure_max_entladeleistung"), 700)

            user_mode = self._state("select.zendure_betriebsmodus") or "Automatik"

            soc_notfall = max(soc_min - 4, 5)

            # ---------------- Preise ----------------
            export = self._attr(
                "sensor.paul_schneider_strasse_39_diagramm_datenexport",
                "data",
            ) or []

            prices = [_f(p.get("price_per_kwh")) for p in export if "price_per_kwh" in p]

            idx = int(((dt_util.now().hour * 60) + dt_util.now().minute) // 15)
            future = prices[idx:] if idx < len(prices) else []

            if future:
                minp = min(future)
                maxp = max(future)
                avgp = sum(future) / len(future)
                dyn_expensive = avgp + (maxp - minp) * 0.25
                expensive = max(expensive_fixed, dyn_expensive)
            else:
                minp = maxp = avgp = price_now
                expensive = expensive_fixed

            surplus = max(pv - load, 0)

            # ---------------- KI Entscheidung ----------------
            ai_status = "standby"
            recommendation = "standby"
            ac_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # ❗ MANUELL: KI greift NICHT ein
            if user_mode == "Manuell":
                ai_status = "manuell"
                recommendation = "manuell"

            # Notfall
            elif soc <= soc_notfall and soc < soc_max:
                ai_status = "notladung"
                recommendation = "billig_laden"
                ac_mode = "input"
                in_w = min(max_charge, 300)

            # Teuer
            elif price_now >= expensive:
                if soc > soc_min:
                    ai_status = "teuer_entladen"
                    recommendation = "entladen"
                    ac_mode = "output"
                    out_w = min(max_discharge, max(load - pv, 0))
                else:
                    ai_status = "teuer_schutz"
                    recommendation = "standby"

            # Günstig
            elif future and future[0] == min(future) and soc < soc_max:
                ai_status = "günstig_laden"
                recommendation = "ki_laden"
                ac_mode = "input"
                in_w = max_charge

            # PV Überschuss
            elif surplus > 100 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                ac_mode = "input"
                in_w = min(max_charge, surplus)

            # ---------------- Recommendation-Freeze ----------------
            now = self._now_ts()
            if self._freeze_until and now < self._freeze_until:
                recommendation = self._last_recommendation or recommendation
            else:
                if recommendation != self._last_recommendation:
                    self._freeze_until = now + 300  # 5 Minuten Freeze
                    self._last_recommendation = recommendation

            # ---------------- Steuerung anwenden ----------------
            if recommendation not in ("standby", "manuell"):
                await self._set_ac_mode(ac_mode)
                await self._set_input_limit(in_w)
                await self._set_output_limit(out_w)

            # ---------------- Rückgabe ----------------
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
                    "expensive_threshold": expensive,
                    "user_mode": user_mode,
                },
            }

        except Exception as err:
            raise UpdateFailed(err)
