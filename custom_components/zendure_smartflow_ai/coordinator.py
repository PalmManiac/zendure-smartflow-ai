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
FREEZE_SECONDS = 120          # Recommendation-Freeze


# =========================
# Entity IDs
# =========================
@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str

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
def _f(state: Any, default: float = 0.0) -> float:
    try:
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

        # Freeze
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

    def _attr(self, entity_id: str, attr: str) -> Any:
        s = self.hass.states.get(entity_id)
        return None if s is None else s.attributes.get(attr)

    # -------------------------
    # Price handling (CORRECT!)
    # -------------------------
    def _prices_with_index(self) -> tuple[float | None, list[float], int]:
        export = self._attr(self.entities.price_export, "data")
        if not export:
            return None, [], 0

        prices: list[float] = []
        for item in export:
            prices.append(_f(item.get("price_per_kwh"), 0.0))

        now = dt_util.now()  # lokale Zeit!
        minutes = now.hour * 60 + now.minute
        idx = minutes // 15

        if idx >= len(prices):
            return None, prices, idx

        return prices[idx], prices, idx

    # -------------------------
    # Hardware control
    # -------------------------
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

            soc_min = _f(self._state(self.entities.soc_min), 12)
            soc_max = _f(self._state(self.entities.soc_max), 95)

            expensive_threshold = _f(self._state(self.entities.expensive_threshold), 0.35)
            max_charge = _f(self._state(self.entities.max_charge), 2000)
            max_discharge = _f(self._state(self.entities.max_discharge), 700)

            surplus = max(pv - load, 0)
            soc_notfall = max(soc_min - 4, 5)

            # --- Preise ---
            price_now, prices_all, idx = self._prices_with_index()
            if price_now is None:
                return {
                    "ai_status": "preis_unbekannt",
                    "recommendation": "standby",
                    "debug": "PRICE_INVALID",
                }

            future = prices_all[idx:]
            minp = min(future) if future else price_now
            maxp = max(future) if future else price_now
            avgp = sum(future) / len(future) if future else price_now
            span = maxp - minp
            expensive = max(expensive_threshold, avgp + span * 0.25)

            # =========================
            # Entscheidungslogik
            # =========================
            ai_status = "standby"
            recommendation = "standby"

            ac_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # 1️⃣ NOTFALL – IMMER Vorrang
            if soc <= soc_notfall:
                ai_status = "notladung"
                recommendation = "billig_laden"
                ac_mode = "input"
                in_w = min(max_charge, 300)

            # 2️⃣ TEUER → ENTLADE
            elif price_now >= expensive and soc > soc_min:
                ai_status = "teuer_jetzt"
                recommendation = "entladen"
                ac_mode = "output"
                need = max(load - pv, 0)
                out_w = min(max_discharge, need)

            # 3️⃣ PV-Überschuss
            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                ac_mode = "input"
                in_w = min(max_charge, surplus)

            # =========================
            # Recommendation Freeze
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
            await self._set_ac_mode(ac_mode)
            await self._set_input(in_w)
            await self._set_output(out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "price_now": round(price_now, 4),
                    "expensive_threshold": round(expensive, 4),
                    "soc": round(soc, 2),
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "pv": pv,
                    "load": load,
                    "surplus": surplus,
                    "set_mode": ac_mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                    "freeze_until": self._freeze_until.isoformat() if self._freeze_until else None,
                    "price_index": idx,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
