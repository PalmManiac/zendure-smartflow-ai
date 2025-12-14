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
        if state is None:
            return default
        return float(str(state).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        data = entry.data or {}
        self.entities = EntityIds(
            soc=data.get("soc_entity", DEFAULT_ENTITY_IDS.soc),
            pv=data.get("pv_entity", DEFAULT_ENTITY_IDS.pv),
            load=data.get("load_entity", DEFAULT_ENTITY_IDS.load),
            price_now=data.get("price_now_entity", DEFAULT_ENTITY_IDS.price_now),
            price_export=data.get("price_export_entity", DEFAULT_ENTITY_IDS.price_export),
            soc_min=data.get("soc_min_entity", DEFAULT_ENTITY_IDS.soc_min),
            soc_max=data.get("soc_max_entity", DEFAULT_ENTITY_IDS.soc_max),
            expensive_threshold=data.get("expensive_threshold_entity", DEFAULT_ENTITY_IDS.expensive_threshold),
            max_charge=data.get("max_charge_entity", DEFAULT_ENTITY_IDS.max_charge),
            max_discharge=data.get("max_discharge_entity", DEFAULT_ENTITY_IDS.max_discharge),
            ac_mode=data.get("ac_mode_entity", DEFAULT_ENTITY_IDS.ac_mode),
            input_limit=data.get("input_limit_entity", DEFAULT_ENTITY_IDS.input_limit),
            output_limit=data.get("output_limit_entity", DEFAULT_ENTITY_IDS.output_limit),
        )

        self._last_mode: str | None = None
        self._last_in: float | None = None
        self._last_out: float | None = None
        self._last_recommendation: str | None = None  # 🔒 Freeze

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    def _get_state(self, entity_id: str) -> str | None:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _get_attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    async def _set_mode(self, mode: str) -> None:
        if mode != self._last_mode:
            await self.hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": self.entities.ac_mode, "option": mode},
                blocking=False,
            )
            self._last_mode = mode

    async def _set_limits(self, in_w: float, out_w: float) -> None:
        if self._last_in is None or abs(self._last_in - in_w) > 25:
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": self.entities.input_limit, "value": round(in_w)},
                blocking=False,
            )
            self._last_in = in_w

        if self._last_out is None or abs(self._last_out - out_w) > 25:
            await self.hass.services.async_call(
                "number", "set_value",
                {"entity_id": self.entities.output_limit, "value": round(out_w)},
                blocking=False,
            )
            self._last_out = out_w

    def _extract_prices(self) -> list[float]:
        export = self._get_attr(self.entities.price_export, "data")
        if not export:
            return []
        return [_f(e.get("price_per_kwh"), 0.0) for e in export]

    def _idx_now(self) -> int:
        now = dt_util.now()
        return (now.hour * 60 + now.minute) // 15

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            soc = _f(self._get_state(self.entities.soc))
            pv = _f(self._get_state(self.entities.pv))
            load = _f(self._get_state(self.entities.load))
            price_now = _f(self._get_state(self.entities.price_now))

            soc_min = _f(self._get_state(self.entities.soc_min), 12)
            soc_max = _f(self._get_state(self.entities.soc_max), 95)
            soc_notfall = max(soc_min - 4, 5)

            max_charge = _f(self._get_state(self.entities.max_charge), 2000)
            max_discharge = _f(self._get_state(self.entities.max_discharge), 700)
            expensive_fixed = _f(self._get_state(self.entities.expensive_threshold), 0.35)

            prices = self._extract_prices()
            idx = self._idx_now()
            future = prices[idx:] if idx < len(prices) else []

            if future:
                avg = sum(future) / len(future)
                span = max(future) - min(future)
                expensive = max(expensive_fixed, avg + span * 0.25)
                cheapest = min(future)
                cheapest_idx = future.index(cheapest)
            else:
                expensive = expensive_fixed
                cheapest_idx = None

            surplus = max(pv - load, 0)

            ai_status = "standby"
            new_recommendation: str | None = None
            mode = "input"
            in_w = 0.0
            out_w = 0.0

            # 🔴 Notfall
            if soc <= soc_notfall and soc < soc_max:
                ai_status = "notladung"
                new_recommendation = "billig_laden"
                in_w = min(max_charge, 300)

            # 🔥 Teuer
            elif price_now >= expensive:
                if soc > soc_min:
                    ai_status = "teuer_entladen"
                    new_recommendation = "entladen"
                    mode = "output"
                    out_w = min(max_discharge, max(load - pv, 0))
                else:
                    ai_status = "teuer_schutz"
                    new_recommendation = "standby"

            # 🟢 Günstigste Phase
            elif cheapest_idx == 0 and soc < soc_max:
                ai_status = "guenstig_laden"
                new_recommendation = "ki_laden"
                in_w = max_charge

            # ☀️ PV Überschuss
            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                new_recommendation = "laden"
                in_w = min(max_charge, surplus)

            else:
                new_recommendation = "standby"

            # 🧊 Recommendation-Freeze
            if self._last_recommendation is None:
                recommendation = new_recommendation
            elif new_recommendation in ("billig_laden", "entladen"):
                recommendation = new_recommendation
            elif new_recommendation != self._last_recommendation:
                recommendation = new_recommendation
            else:
                recommendation = self._last_recommendation

            self._last_recommendation = recommendation

            await self._set_mode(mode)
            await self._set_limits(in_w, out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "soc": soc,
                    "price_now": price_now,
                    "expensive": expensive,
                    "cheapest_idx": cheapest_idx,
                    "pv": pv,
                    "load": load,
                    "surplus": surplus,
                    "set_input": in_w,
                    "set_output": out_w,
                },
            }

        except Exception as err:
            raise UpdateFailed(err) from err
