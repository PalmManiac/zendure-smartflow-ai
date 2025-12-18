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

UPDATE_INTERVAL = 10
FREEZE_SECONDS = 120


# ======================================================
# Entity IDs
# ======================================================
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


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entities = DEFAULT_ENTITY_IDS

        self._freeze_until: datetime | None = None
        self._last_ai_status: str | None = None
        self._last_recommendation: str | None = None

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # --------------------------------------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # --------------------------------------------------
    def _get_price_now(self) -> float | None:
        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list):
            return None
        idx = (dt_util.now().hour * 60 + dt_util.now().minute) // 15
        try:
            return _to_float(export[idx].get("price_per_kwh"), None)
        except Exception:
            return None

    # ==================================================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            # --- Read states ---
            soc = _to_float(self._state(self.entities.soc))
            pv = _to_float(self._state(self.entities.pv))
            load = _to_float(self._state(self.entities.load))
            price_now = self._get_price_now()

            ac_mode_current = self._state(self.entities.ac_mode)

            # ==================================================
            # 🔒 MANUAL MODE PROTECTION
            # ==================================================
            if ac_mode_current not in ("input", "output"):
                return {
                    "ai_status": "manual_mode",
                    "recommendation": "manuell",
                    "debug": "MANUAL_MODE_ACTIVE",
                }

            if price_now is None:
                return {
                    "ai_status": "price_invalid",
                    "recommendation": "standby",
                    "debug": "PRICE_INVALID",
                }

            soc_min = _to_float(self._state(self.entities.soc_min), 12.0)
            soc_max = _to_float(self._state(self.entities.soc_max), 100.0)
            expensive = _to_float(self._state(self.entities.expensive_threshold), 0.35)
            max_charge = _to_float(self._state(self.entities.max_charge), 2000)
            max_discharge = _to_float(self._state(self.entities.max_discharge), 700)

            surplus = max(pv - load, 0)
            soc_notfall = max(soc_min - 4, 5)

            ai_status = "standby"
            recommendation = "standby"
            ac_mode = ac_mode_current
            in_w = 0.0
            out_w = 0.0

            # ==================================================
            # PRIORITY LOGIC
            # ==================================================
            if price_now >= expensive and soc > soc_min:
                ai_status = "teuer_jetzt"
                recommendation = "entladen"
                ac_mode = "output"
                out_w = min(max_discharge, max(load - pv, 0))

            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                ac_mode = "input"
                in_w = min(max_charge, surplus)

            elif soc <= soc_notfall and soc < soc_min:
                ai_status = "notladung"
                recommendation = "billig_laden"
                ac_mode = "input"
                in_w = min(max_charge, 300)

            # ==================================================
            # Freeze (Anzeige only)
            # ==================================================
            if self._freeze_until and now < self._freeze_until:
                ai_status = self._last_ai_status or ai_status
                recommendation = self._last_recommendation or recommendation
            else:
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation

            # ==================================================
            # Apply ONLY if AI controls
            # ==================================================
            if ac_mode != ac_mode_current:
                await self.hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": self.entities.ac_mode, "option": ac_mode},
                    blocking=False,
                )

            if ac_mode == "input":
                await self.hass.services.async_call(
                    "number",
                    "set_value",
                    {"entity_id": self.entities.input_limit, "value": round(in_w, 0)},
                    blocking=False,
                )

            if ac_mode == "output":
                await self.hass.services.async_call(
                    "number",
                    "set_value",
                    {"entity_id": self.entities.output_limit, "value": round(out_w, 0)},
                    blocking=False,
                )

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
