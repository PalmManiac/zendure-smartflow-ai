from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

FREEZE_SECONDS = 120
CHANGE_TOLERANCE_W = 25  # Anti-Flattern


def _f(state: str | None, default: float = 0.0) -> float:
    try:
        return float(str(state).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """KI + Hardware-Steuerung für Zendure SmartFlow AI"""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        # Recommendation-Freeze
        self._last_recommendation: str | None = None
        self._last_ai_status: str | None = None
        self._freeze_until = None

        # Hardware Anti-Flattern
        self._last_mode: str | None = None
        self._last_in: float | None = None
        self._last_out: float | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    # ------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------

    def _state(self, entity_id: str) -> str | None:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    def _prices_future(self) -> list[float]:
        export = self._attr(
            "sensor.paul_schneider_strasse_39_diagramm_datenexport", "data"
        )
        if not export:
            return []

        prices = [_f(e.get("price_per_kwh"), 0.0) for e in export]
        now = dt_util.now()
        idx = (now.hour * 60 + now.minute) // 15
        return prices[idx:]

    # ------------------------------------------------------------
    # Hardware Calls
    # ------------------------------------------------------------

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

    async def _apply_hardware(
        self, mode: str, in_w: float, out_w: float
    ) -> None:
        def changed(a: float | None, b: float) -> bool:
            if a is None:
                return True
            return abs(a - b) > CHANGE_TOLERANCE_W

        # Mode
        if mode != self._last_mode:
            await self._set_ac_mode(mode)
            self._last_mode = mode

        # Input
        if changed(self._last_in, in_w):
            await self._set_input_limit(in_w)
            self._last_in = in_w

        # Output
        if changed(self._last_out, out_w):
            await self._set_output_limit(out_w)
            self._last_out = out_w

    # ------------------------------------------------------------
    # Core
    # ------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            # -------- Basis --------
            soc = _f(self._state("sensor.solarflow_2400_ac_electric_level"))
            pv = _f(self._state("sensor.sb2_5_1vl_40_401_pv_power"))
            load = _f(self._state("sensor.gesamtverbrauch"))
            price_now = _f(
                self._state(
                    "sensor.paul_schneider_strasse_39_aktueller_strompreis_energie_dashboard"
                )
            )

            soc_min = _f(self._state("number.zendure_soc_min"), 12)
            soc_max = _f(self._state("number.zendure_soc_max"), 95)
            max_charge = _f(self._state("number.zendure_max_ladeleistung"), 2000)
            max_discharge = _f(self._state("number.zendure_max_entladeleistung"), 700)

            mode = self._state("select.zendure_betriebsmodus") or "automatic"

            prices = self._prices_future()

            minp = min(prices) if prices else price_now
            maxp = max(prices) if prices else price_now
            avgp = sum(prices) / len(prices) if prices else price_now
            span = maxp - minp
            expensive = max(0.35, avgp + span * 0.25)

            surplus = max(pv - load, 0)
            net_load = max(load - pv, 0)

            # -------- Defaults --------
            ai_status = "standby"
            recommendation = "standby"
            allow_control = True

            hw_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # ======================================================
            # MANUELL
            # ======================================================
            if mode == "manual":
                ai_status = "manual_mode"
                recommendation = "manual"
                allow_control = False

            # ======================================================
            # SOMMER
            # ======================================================
            elif mode == "summer":
                if surplus > 80 and soc < soc_max:
                    ai_status = "pv_laden"
                    recommendation = "laden"
                    hw_mode = "input"
                    in_w = min(max_charge, surplus)

            # ======================================================
            # WINTER
            # ======================================================
            elif mode == "winter":
                if price_now >= expensive and soc > soc_min:
                    ai_status = "teuer_entladen"
                    recommendation = "entladen"
                    hw_mode = "output"
                    out_w = min(max_discharge, net_load)
                elif prices and prices[0] == minp and soc < soc_max:
                    ai_status = "günstig_laden"
                    recommendation = "billig_laden"
                    hw_mode = "input"
                    in_w = max_charge

            # ======================================================
            # AUTOMATIC
            # ======================================================
            else:
                if soc <= max(soc_min - 4, 5):
                    ai_status = "notladung"
                    recommendation = "billig_laden"
                    hw_mode = "input"
                    in_w = min(max_charge, 300)
                    self._freeze_until = None

                elif price_now >= expensive and soc > soc_min:
                    ai_status = "teuer_entladen"
                    recommendation = "entladen"
                    hw_mode = "output"
                    out_w = min(max_discharge, net_load)

                elif prices and prices[0] == minp and soc < soc_max:
                    ai_status = "günstig_laden"
                    recommendation = "ki_laden"
                    hw_mode = "input"
                    in_w = max_charge

                elif surplus > 80 and soc < soc_max:
                    ai_status = "pv_laden"
                    recommendation = "laden"
                    hw_mode = "input"
                    in_w = min(max_charge, surplus)

            # ======================================================
            # Recommendation-Freeze
            # ======================================================
            if allow_control:
                if self._freeze_until and now < self._freeze_until:
                    recommendation = self._last_recommendation
                    ai_status = self._last_ai_status
                else:
                    self._last_recommendation = recommendation
                    self._last_ai_status = ai_status
                    self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)

                await self._apply_hardware(hw_mode, in_w, out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "mode": mode,
                    "price_now": price_now,
                    "min_price": minp,
                    "max_price": maxp,
                    "avg_price": avgp,
                    "expensive_threshold": expensive,
                    "surplus": surplus,
                    "net_load": net_load,
                    "soc": soc,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "set_mode": hw_mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
