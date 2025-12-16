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

FREEZE_SECONDS = 120  # Recommendation-Freeze (nur ruhige Phasen!)

# =========================
# Entity Definition
# =========================
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


# =========================
# Helper
# =========================
def _f(val: str | None, default: float = 0.0) -> float:
    try:
        return float(str(val).replace(",", "."))
    except Exception:
        return default


# =========================
# Coordinator
# =========================
class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id
        self.entities = DEFAULT_ENTITY_IDS

        # Recommendation-Freeze intern
        self._last_recommendation: str | None = None
        self._last_ai_status: str | None = None
        self._freeze_until: datetime | None = None

        # Hardware-Spam-Schutz
        self._last_mode: str | None = None
        self._last_in: float | None = None
        self._last_out: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    # =========================
    # HA State Access
    # =========================
    def _state(self, entity_id: str) -> str | None:
        s = self.hass.states.get(entity_id)
        return None if s is None else s.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        s = self.hass.states.get(entity_id)
        return None if s is None else s.attributes.get(attr)

    # =========================
    # Price handling
    # =========================
    def _future_prices(self) -> list[float]:
        export = self._attr(self.entities.price_export, "data")
        if not export:
            return []

        prices = [_f(e.get("price_per_kwh")) for e in export]
        now = dt_util.now()
        idx = (now.hour * 60 + now.minute) // 15
        return prices[idx:]

    # =========================
    # Hardware Control
    # =========================
    async def _apply_control(self, mode: str, in_w: float, out_w: float) -> None:
        def changed(a: float | None, b: float, tol: float) -> bool:
            return a is None or abs(a - b) > tol

        if mode != self._last_mode:
            await self.hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": self.entities.ac_mode, "option": mode},
                blocking=False,
            )
            self._last_mode = mode

        if changed(self._last_in, in_w, 25):
            await self.hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": self.entities.input_limit, "value": round(in_w)},
                blocking=False,
            )
            self._last_in = in_w

        if changed(self._last_out, out_w, 25):
            await self.hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": self.entities.output_limit, "value": round(out_w)},
                blocking=False,
            )
            self._last_out = out_w

    # =========================
    # Main Logic
    # =========================
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
            max_charge = _f(self._state(self.entities.max_charge), 2000)
            max_discharge = _f(self._state(self.entities.max_discharge), 700)

            prices = self._future_prices()
            minp = min(prices) if prices else price_now
            maxp = max(prices) if prices else price_now
            avgp = sum(prices) / len(prices) if prices else price_now
            span = maxp - minp
            expensive = max(expensive_fixed, avgp + span * 0.25)

            surplus = max(pv - load, 0)

            # =========================
            # Decision
            # =========================
            ai_status = "standby"
            recommendation = "standby"
            mode = "input"
            in_w = 0.0
            out_w = 0.0

            if soc <= soc_notfall:
                ai_status = "notladung"
                recommendation = "billig_laden"
                mode = "input"
                in_w = min(max_charge, 300)

            elif price_now >= expensive_fixed and soc > soc_min:
                ai_status = "teuer_jetzt"
                recommendation = "entladen"
                mode = "output"
                out_w = min(max_discharge, max(load - pv, 0))

            elif prices and prices[0] == minp and soc < soc_max:
                ai_status = "günstig_jetzt"
                recommendation = "ki_laden"
                mode = "input"
                in_w = max_charge

            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                mode = "input"
                in_w = min(max_charge, surplus)

            # =========================
            # Recommendation-Freeze (FIX)
            # =========================
            force_override = price_now >= expensive or soc <= soc_notfall

            if force_override:
                self._freeze_until = None
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation

            elif self._freeze_until and now < self._freeze_until:
                ai_status = self._last_ai_status
                recommendation = self._last_recommendation

            else:
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)

            # =========================
            # Apply Hardware Control
            # =========================
            await self._apply_control(mode, in_w, out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "price_now": round(price_now, 4),
                    "expensive": round(expensive, 4),
                    "soc": soc,
                    "pv": pv,
                    "load": load,
                    "surplus": surplus,
                    "freeze_until": self._freeze_until.isoformat() if self._freeze_until else None,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
