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

UPDATE_INTERVAL = 10          # Sekunden
FREEZE_SECONDS = 120          # Recommendation-Freeze (nur Anzeige!)

EMERGENCY_OFFSET = 4          # % unter soc_min
EMERGENCY_MIN = 5             # niemals unter 5 %


# =========================
# Entity IDs
# =========================
@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str
    price_now: str

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
def _f(state: str | None, default: float = 0.0) -> float:
    try:
        if state is None:
            return default
        return float(str(state).replace(",", "."))
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

        # Recommendation-Freeze (NUR TEXT)
        self._freeze_until: datetime | None = None
        self._last_recommendation: str | None = None
        self._last_ai_status: str | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # -------------------------
    # State helpers
    # -------------------------
    def _state(self, entity_id: str) -> str | None:
        s = self.hass.states.get(entity_id)
        return None if s is None else s.state

    async def _set_ac_mode(self, mode: str) -> None:
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": round(watts, 0)},
            blocking=False,
        )

    async def _set_output(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": round(watts, 0)},
            blocking=False,
        )

    # =========================
    # Main update
    # =========================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            # --- Basiswerte ---
            soc = _f(self._state(self.entities.soc))
            pv = _f(self._state(self.entities.pv))
            load = _f(self._state(self.entities.load))
            price_now = _f(self._state(self.entities.price_now))

            soc_min = _f(self._state(self.entities.soc_min), 12)
            soc_max = _f(self._state(self.entities.soc_max), 95)

            expensive = _f(self._state(self.entities.expensive_threshold), 0.35)

            max_charge = _f(self._state(self.entities.max_charge), 2000)
            max_discharge = _f(self._state(self.entities.max_discharge), 700)

            surplus = max(pv - load, 0)

            # --- Grenzen ---
            soc_notfall = max(soc_min - EMERGENCY_OFFSET, EMERGENCY_MIN)

            # =========================
            # Entscheidungslogik (FIX)
            # =========================
            ai_status = "standby"
            recommendation = "standby"

            ac_mode: str | None = None
            in_w = 0.0
            out_w = 0.0

            # 🔥 1) TEUER → IMMER ENTLADE (höchste Priorität)
            if price_now >= expensive and soc > soc_min:
                ai_status = "teuer_jetzt"
                recommendation = "entladen"
                ac_mode = "output"
                out_w = min(max_discharge, max(load - pv, 0))
                in_w = 0

            # 🔋 2) NOTLADEN (nur bei echtem Notfall)
            elif soc <= soc_notfall:
                ai_status = "notladung"
                recommendation = "billig_laden"
                ac_mode = "input"
                in_w = min(max_charge, 300)
                out_w = 0

            # ☀️ 3) PV-Überschuss
            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                ac_mode = "input"
                in_w = min(max_charge, surplus)
                out_w = 0

            # =========================
            # Recommendation-Freeze
            # (NUR Anzeige, KEINE Hardware!)
            # =========================
            if self._freeze_until and now < self._freeze_until:
                ai_status = self._last_ai_status or ai_status
                recommendation = self._last_recommendation or recommendation
            else:
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation

            # =========================
            # Hardware anwenden
            # =========================
            if ac_mode == "output":
                await self._set_ac_mode("output")
                await self._set_output(out_w)
                await self._set_input(0)

            elif ac_mode == "input":
                await self._set_ac_mode("input")
                await self._set_input(in_w)
                await self._set_output(0)

            # Standby → nichts anfassen

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "price_now": price_now,
                    "expensive_threshold": expensive,
                    "soc": soc,
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "soc_notfall": soc_notfall,
                    "pv": pv,
                    "load": load,
                    "surplus": surplus,
                    "set_mode": ac_mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                    "freeze_until": self._freeze_until.isoformat() if self._freeze_until else None,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
