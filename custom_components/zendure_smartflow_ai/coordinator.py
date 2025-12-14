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
    # Messwerte
    soc: str
    pv: str
    load: str
    price_now: str
    price_export: str

    # Schwellen / Parameter (Helfer)
    soc_min: str
    soc_max: str
    expensive_threshold: str
    max_charge: str
    max_discharge: str

    # Zendure Steuer-Entitäten
    ac_mode: str
    input_limit: str
    output_limit: str

# in _async_update_data() oder beim Initialisieren
data.setdefault("mode", MODE_AUTOMATIC)

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
    """Coordinator = Daten holen + Entscheidung + direkte Steuerung."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id  # wichtig für unique_id in sensor.py

        # Entity-IDs: erst aus ConfigEntry, sonst Defaults
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

        # interner Schutz gegen „Service-Spam“
        self._last_mode: str | None = None
        self._last_in: float | None = None
        self._last_out: float | None = None

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
        if st is None:
            return None
        return st.attributes.get(attr)

    async def _set_mode_input(self) -> None:
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": "input"},
            blocking=False,
        )

    async def _set_mode_output(self) -> None:
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": "output"},
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": float(round(watts, 0))},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": float(round(watts, 0))},
            blocking=False,
        )

    async def _apply_control(self, mode: str, in_w: float, out_w: float) -> None:
        """
        Apply only if changed enough -> verhindert Flattern & Log-Spam.
        """
        # kleine Totzone
        def changed(a: float | None, b: float, tol: float) -> bool:
            if a is None:
                return True
            return abs(a - b) > tol

        # Mode setzen
        if mode != self._last_mode:
            if mode == "input":
                await self._set_mode_input()
            elif mode == "output":
                await self._set_mode_output()
            self._last_mode = mode

        # Limits setzen (nur wenn geändert)
        if changed(self._last_in, in_w, 25):
            await self._set_input_limit(in_w)
            self._last_in = in_w

        if changed(self._last_out, out_w, 25):
            await self._set_output_limit(out_w)
            self._last_out = out_w

    def _extract_prices(self) -> list[float]:
        """
        Aus Tibber Datenexport:
        attributes.data = [{start_time:..., price_per_kwh: 0.287}, ...]
        """
        export = self._get_attr(self.entities.price_export, "data")
        if not export:
            return []

        prices: list[float] = []
        try:
            for item in export:
                p = item.get("price_per_kwh")
                prices.append(_f(p, 0.0))
        except Exception:
            return []
        return prices

    def _idx_now_15min(self) -> int:
        # Export beginnt um 00:00 lokaler Zeit. Index ab Mitternacht in 15-Minuten-Slots.
        now = dt_util.now()
        minutes = (now.hour * 60) + now.minute
        return int(minutes // 15)


    def _find_first_peak_start(self, future: list[float], expensive: float) -> int | None:
        for i, p in enumerate(future):
            if p >= expensive:
                return i
        return None

    def _find_cheapest_before_peak(self, future: list[float], peak_start: int | None) -> tuple[int | None, float | None]:
        if not future:
            return None, None
        if peak_start is None or peak_start <= 0:
            # kein Peak -> günstigste Phase in den nächsten 24h (oder wieviel future liefert)
            m = min(future)
            return future.index(m), m
        window = future[:peak_start]  # nur VOR dem Peak
        if not window:
            return None, None
        m = min(window)
        return window.index(m), m

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # --- Basiswerte lesen ---
            soc = _f(self._get_state(self.entities.soc), 0.0)
            pv = _f(self._get_state(self.entities.pv), 0.0)
            load = _f(self._get_state(self.entities.load), 0.0)
            price_now = _f(self._get_state(self.entities.price_now), 0.0)

            soc_min = _f(self._get_state(self.entities.soc_min), 12.0)
            soc_max = _f(self._get_state(self.entities.soc_max), 95.0)

            # Notfallgrenze: 4% unter Reserve, aber nie < 5%
            soc_notfall = max(soc_min - 4.0, 5.0)

            expensive_threshold = _f(self._get_state(self.entities.expensive_threshold), 0.35)

            max_charge = _f(self._get_state(self.entities.max_charge), 2000.0)
            max_discharge = _f(self._get_state(self.entities.max_discharge), 700.0)

            # --- Preisreihe ---
            prices_all = self._extract_prices()
            idx = self._idx_now_15min()
            future = prices_all[idx:] if idx < len(prices_all) else []

            # dynamische Schwelle (optional) + feste Schwelle, wir nehmen das strengere
            if future:
                minp = min(future)
                maxp = max(future)
                avg = sum(future) / len(future)
                span = maxp - minp
                dynamic_expensive = avg + span * 0.25
                expensive = max(expensive_threshold, dynamic_expensive)
            else:
                minp = price_now
                maxp = price_now
                avg = price_now
                span = 0.0
                dynamic_expensive = expensive_threshold
                expensive = expensive_threshold

            # --- Peak & cheapest-before-peak ---
            peak_start = self._find_first_peak_start(future, expensive) if future else None
            cheapest_idx, cheapest_price = self._find_cheapest_before_peak(future, peak_start)

            # „Sind wir gerade im billigsten Slot?“
            in_cheapest_slot = (cheapest_idx == 0) if cheapest_idx is not None else False

            # PV Überschuss
            surplus = max(pv - load, 0.0)

            # --- Entscheidung (V0.1 Core) ---
            ai_status = "standby"
            recommendation = "standby"
            control_mode = "input"  # input/output
            in_w = 0.0
            out_w = 0.0

            # 1) Harte Notladung
            if soc <= soc_notfall and soc < soc_max:
                ai_status = "notladung_aktiv"
                recommendation = "billig_laden"
                control_mode = "input"
                in_w = max(0.0, min(max_charge, 300.0))  # konservativ
                out_w = 0.0

            # 2) Teuer jetzt -> entladen wenn möglich, sonst Schutz
            elif price_now >= expensive:
                if soc <= soc_min:
                    ai_status = "teuer_jetzt_akkuschutz"
                    recommendation = "standby"
                    control_mode = "input"
                    in_w = 0.0
                    out_w = 0.0
                else:
                    ai_status = "teuer_jetzt_entladen"
                    recommendation = "entladen"
                    control_mode = "output"
                    # simple: decke Hauslast (netto) ab
                    need = max(load - pv, 0.0)
                    out_w = min(max_discharge, need)
                    in_w = 0.0

            # 3) Wenn wir im billigsten Slot (vor Peak oder allgemein) sind -> aktiv laden
            elif in_cheapest_slot and soc < soc_max:
                ai_status = "günstig_jetzt_laden"
                recommendation = "ki_laden"
                control_mode = "input"
                in_w = max_charge
                out_w = 0.0

            # 4) PV-Überschuss -> laden (sanft)
            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_überschuss_laden"
                recommendation = "laden"
                control_mode = "input"
                in_w = min(max_charge, max(0.0, surplus))
                out_w = 0.0

            # 5) Sonst standby
            else:
                # falls SoC unter Reserve: niemals entladen
                ai_status = "standby"
                recommendation = "standby"
                control_mode = "input"
                in_w = 0.0
                out_w = 0.0

            # --- Steuerung anwenden ---
            # Wichtig: nur steuern, wenn Limits/Mode vorhanden sind
            await self._apply_control(control_mode, in_w, out_w)

            details = {
                "price_now": round(price_now, 4),
                "min_price_future": round(minp, 4),
                "max_price_future": round(maxp, 4),
                "avg_price_future": round(avg, 4),
                "expensive_threshold_effective": round(expensive, 4),
                "expensive_threshold_fixed": round(expensive_threshold, 4),
                "expensive_threshold_dynamic": round(dynamic_expensive, 4),
                "idx_now": idx,
                "future_len": len(future),
                "peak_start_idx": peak_start,
                "cheapest_idx": cheapest_idx,
                "cheapest_price": cheapest_price,
                "soc": round(soc, 2),
                "soc_min": round(soc_min, 2),
                "soc_max": round(soc_max, 2),
                "soc_notfall": round(soc_notfall, 2),
                "pv": round(pv, 1),
                "load": round(load, 1),
                "surplus": round(surplus, 1),
                "max_charge": round(max_charge, 0),
                "max_discharge": round(max_discharge, 0),
                "set_mode": control_mode,
                "set_input_w": round(in_w, 0),
                "set_output_w": round(out_w, 0),
            }

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": details,
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
