from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    # config keys
    CONF_SOC_ENTITY, CONF_PV_ENTITY, CONF_LOAD_ENTITY, CONF_PRICE_EXPORT_ENTITY,
    CONF_AC_MODE_ENTITY, CONF_INPUT_LIMIT_ENTITY, CONF_OUTPUT_LIMIT_ENTITY,
    # defaults / settings keys
    DEFAULT_SOC_MIN, DEFAULT_SOC_MAX, DEFAULT_MAX_CHARGE, DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD, DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_FREEZE_SECONDS, DEFAULT_UPDATE_INTERVAL,
    SETTING_SOC_MIN, SETTING_SOC_MAX, SETTING_MAX_CHARGE, SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD, SETTING_VERY_EXPENSIVE_THRESHOLD, SETTING_FREEZE_SECONDS,
    SETTING_AI_MODE, SETTING_MANUAL_ACTION,
    # modes / actions
    AI_MODE_AUTOMATIC, AI_MODE_SUMMER, AI_MODE_WINTER, AI_MODE_MANUAL,
    MANUAL_STANDBY, MANUAL_CHARGE, MANUAL_DISCHARGE,
    # statuses / recs
    STATUS_INIT, STATUS_OK, STATUS_SENSOR_INVALID, STATUS_PRICE_INVALID, STATUS_MANUAL_ACTIVE,
    REC_STANDBY, REC_CHARGE, REC_DISCHARGE, REC_HOLD,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EntityIds:
    soc: str
    pv: str
    load: str
    price_export: str | None
    ac_mode: str
    input_limit: str
    output_limit: str


def _to_float(val: Any, default: float | None = None) -> float | None:
    try:
        if val is None:
            return default
        s = str(val).strip().replace(",", ".")
        if s.lower() in ("unknown", "unavailable", ""):
            return default
        return float(s)
    except Exception:
        return default


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _chunks(it: Iterable[float], size: int) -> list[list[float]]:
    buf: list[float] = []
    out: list[list[float]] = []
    for x in it:
        buf.append(x)
        if len(buf) >= size:
            out.append(buf)
            buf = []
    if buf:
        out.append(buf)
    return out


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    V0.7.0:
    - Preisfenster-/Peak-Erkennung (wenn Preisquelle vorhanden)
    - Preissensor optional: ohne Preis => Sommerlogik (PV/Autarkie) möglich
    - Interne Settings/Modi: keine externen Helper nötig
    - Hardware-Steuerung: ac_mode + input_limit + output_limit
    - Manual Mode: überschreibt Hardware (AI greift nicht rein)
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        data = entry.data or {}

        # Pflichtsensoren
        soc = data.get(CONF_SOC_ENTITY, "")
        pv = data.get(CONF_PV_ENTITY, "")
        load = data.get(CONF_LOAD_ENTITY, "")

        # Optional: Preisexport
        price_export = data.get(CONF_PRICE_EXPORT_ENTITY) or None

        # Pflicht: Zendure Steuerung
        ac_mode = data.get(CONF_AC_MODE_ENTITY, "")
        input_limit = data.get(CONF_INPUT_LIMIT_ENTITY, "")
        output_limit = data.get(CONF_OUTPUT_LIMIT_ENTITY, "")

        self.entities = EntityIds(
            soc=soc,
            pv=pv,
            load=load,
            price_export=price_export,
            ac_mode=ac_mode,
            input_limit=input_limit,
            output_limit=output_limit,
        )

        # Freeze (gegen Flackern)
        self._freeze_until: datetime | None = None
        self._last_status: str = STATUS_INIT
        self._last_rec: str = REC_STANDBY

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )

    # --------------------------------------------------
    # Helpers: states / attrs
    # --------------------------------------------------
    def _state(self, entity_id: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # --------------------------------------------------
    # Entry option helpers (internal settings)
    # --------------------------------------------------
    def _opt_float(self, key: str, default: float) -> float:
        val = self.entry.options.get(key, default)
        f = _to_float(val, default)
        return float(f if f is not None else default)

    def _opt_int(self, key: str, default: int) -> int:
        val = self.entry.options.get(key, default)
        try:
            return int(float(val))
        except Exception:
            return default

    def _opt_str(self, key: str, default: str) -> str:
        v = self.entry.options.get(key)
        return str(v) if v is not None and str(v) != "" else default

    # --------------------------------------------------
    # Price series: Tibber Export attributes.data[]
    # --------------------------------------------------
    def _price_series(self) -> list[float]:
        """
        Returns list of prices (€/kWh) for 15-min slots.
        If no price_export configured or invalid -> [].
        """
        if not self.entities.price_export:
            return []
        data = self._attr(self.entities.price_export, "data")
        if not isinstance(data, list) or not data:
            return []

        prices: list[float] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            p = _to_float(item.get("price_per_kwh"), None)
            if p is None:
                continue
            prices.append(float(p))
        return prices

    def _price_now(self, prices: list[float]) -> tuple[float | None, int | None]:
        if not prices:
            return None, None
        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)
        if idx < 0 or idx >= len(prices):
            return None, None
        return prices[idx], idx

    # --------------------------------------------------
    # Peak & window analysis (simple, stable heuristics)
    # --------------------------------------------------
    def _analyze_prices(self, prices: list[float], idx_now: int) -> dict[str, Any]:
        """
        Produces:
        - min_4h, avg_12h, max_12h
        - is_cheap_now (in next 6h bottom band)
        - is_expensive_now (>= threshold OR near top band)
        - next_peak_idx (next slot within next 12h above very_expensive or top band)
        """
        out: dict[str, Any] = {}

        horizon_6h = 24
        horizon_12h = 48

        future_6h = prices[idx_now: idx_now + horizon_6h]
        future_12h = prices[idx_now: idx_now + horizon_12h]

        if not future_12h:
            return out

        min_6 = min(future_6h) if future_6h else prices[idx_now]
        max_12 = max(future_12h)
        avg_12 = sum(future_12h) / len(future_12h)

        # Bottom band = günstig: <= min_6 + 20% der Spanne in 6h
        span_6 = (max(future_6h) - min(future_6h)) if len(future_6h) > 1 else 0.0
        cheap_band = min_6 + span_6 * 0.20

        # Top band = teuer: >= avg_12 + 30% der Spanne in 12h
        span_12 = max_12 - min(future_12h)
        expensive_band = avg_12 + span_12 * 0.30

        out.update(
            {
                "min_6h": round(min_6, 4),
                "avg_12h": round(avg_12, 4),
                "max_12h": round(max_12, 4),
                "cheap_band": round(cheap_band, 4),
                "expensive_band": round(expensive_band, 4),
            }
        )

        # Next peak within 12h (index offset)
        next_peak: int | None = None
        for off, p in enumerate(future_12h):
            if p >= expensive_band:
                next_peak = idx_now + off
                break
        out["next_peak_idx"] = next_peak
        return out

    # --------------------------------------------------
    # Hardware calls
    # --------------------------------------------------
    async def _set_ac_mode(self, mode: str) -> None:
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": self.entities.ac_mode, "option": mode},
            blocking=False,
        )

    async def _set_input_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.input_limit, "value": round(float(watts), 0)},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": round(float(watts), 0)},
            blocking=False,
        )

    # --------------------------------------------------
    # Main update
    # --------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # Settings (internal)
            soc_min = self._opt_float(SETTING_SOC_MIN, DEFAULT_SOC_MIN)
            soc_max = self._opt_float(SETTING_SOC_MAX, DEFAULT_SOC_MAX)
            max_charge = self._opt_float(SETTING_MAX_CHARGE, DEFAULT_MAX_CHARGE)
            max_discharge = self._opt_float(SETTING_MAX_DISCHARGE, DEFAULT_MAX_DISCHARGE)
            price_thr = self._opt_float(SETTING_PRICE_THRESHOLD, DEFAULT_PRICE_THRESHOLD)
            very_exp = self._opt_float(SETTING_VERY_EXPENSIVE_THRESHOLD, DEFAULT_VERY_EXPENSIVE_THRESHOLD)
            freeze_s = self._opt_int(SETTING_FREEZE_SECONDS, DEFAULT_FREEZE_SECONDS)
            ai_mode = self._opt_str(SETTING_AI_MODE, AI_MODE_AUTOMATIC)
            manual_action = self._opt_str(SETTING_MANUAL_ACTION, MANUAL_STANDBY)

            # Read sensors
            soc_raw = self._state(self.entities.soc)
            pv_raw = self._state(self.entities.pv)
            load_raw = self._state(self.entities.load)

            soc = _to_float(soc_raw, None)
            pv = _to_float(pv_raw, None)
            load = _to_float(load_raw, None)

            if soc is None or pv is None or load is None:
                return {
                    "status": STATUS_SENSOR_INVALID,
                    "recommendation": REC_STANDBY,
                    "debug": "SENSOR_INVALID",
                    "details": {
                        "soc_raw": soc_raw,
                        "pv_raw": pv_raw,
                        "load_raw": load_raw,
                    },
                }

            soc = float(soc)
            pv = float(pv)
            load = float(load)

            surplus = max(pv - load, 0.0)
            deficit = max(load - pv, 0.0)

            # Price optional
            prices = self._price_series()
            price_now, idx_now = self._price_now(prices)

            price_info: dict[str, Any] = {}
            if price_now is not None and idx_now is not None:
                price_info = self._analyze_prices(prices, idx_now)

            # --------------------------------------------------
            # Decide action (recommendation + hardware targets)
            # --------------------------------------------------
            status = STATUS_OK
            rec = REC_STANDBY

            target_mode = "input"     # Zendure select option
            target_in_w = 0.0
            target_out_w = 0.0

            # Manual mode: AI MUST NOT override (außer Standby -> alles 0)
            if ai_mode == AI_MODE_MANUAL:
                status = STATUS_MANUAL_ACTIVE
                if manual_action == MANUAL_CHARGE:
                    rec = REC_CHARGE
                    target_mode = "input"
                    # Lade dynamisch: wenn Überschuss da, nimm surplus, sonst mildes Laden (z.B. 300W)
                    base = surplus if surplus > 50 else 300.0
                    target_in_w = _clamp(base, 0.0, max_charge)
                    target_out_w = 0.0

                elif manual_action == MANUAL_DISCHARGE:
                    rec = REC_DISCHARGE
                    target_mode = "output"
                    # Entlade dynamisch: decke Defizit (falls vorhanden), sonst mild 300W
                    base = deficit if deficit > 50 else 300.0
                    # nur entladen wenn soc > soc_min
                    if soc > soc_min:
                        target_out_w = _clamp(base, 0.0, max_discharge)
                    else:
                        target_out_w = 0.0
                        rec = REC_HOLD
                    target_in_w = 0.0

                else:
                    rec = REC_STANDBY
                    target_mode = "input"
                    target_in_w = 0.0
                    target_out_w = 0.0

            else:
                # AUTOMATIC / SUMMER / WINTER
                # Wenn kein Preis vorhanden: Sommerlogik (PV/Autarkie) ist trotzdem nutzbar
                has_price = price_now is not None

                # Sehr teuer: immer aus Batterie glätten (wenn möglich)
                if has_price and price_now >= very_exp and soc > soc_min:
                    status = "very_expensive"
                    rec = REC_DISCHARGE
                    target_mode = "output"
                    target_out_w = _clamp(deficit if deficit > 50 else max_discharge, 0.0, max_discharge)
                    target_in_w = 0.0

                # WINTER: Preis dominiert
                elif ai_mode == AI_MODE_WINTER:
                    if not has_price:
                        status = STATUS_PRICE_INVALID
                        rec = REC_STANDBY
                    else:
                        # Teuer -> entladen (wenn SoC > min)
                        if price_now >= price_thr and soc > soc_min:
                            status = "expensive_now"
                            rec = REC_DISCHARGE
                            target_mode = "output"
                            target_out_w = _clamp(deficit, 0.0, max_discharge)
                            target_in_w = 0.0

                        # Günstiges Fenster -> laden bis soc_max
                        elif soc < soc_max:
                            cheap_band = _to_float(price_info.get("cheap_band"), None)
                            if cheap_band is not None and price_now <= cheap_band:
                                status = "cheap_window"
                                rec = REC_CHARGE
                                target_mode = "input"
                                # wenn Überschuss da: nutze surplus, sonst moderat laden (z.B. 500W)
                                base = surplus if surplus > 50 else 500.0
                                target_in_w = _clamp(base, 0.0, max_charge)
                                target_out_w = 0.0

                        # sonst standby
                        else:
                            rec = REC_STANDBY

                # SUMMER: Autarkie dominiert (PV laden, abends bei Defizit entladen)
                elif ai_mode == AI_MODE_SUMMER:
                    # PV-Überschuss laden
                    if surplus > 80 and soc < soc_max:
                        status = "pv_surplus"
                        rec = REC_CHARGE
                        target_mode = "input"
                        target_in_w = _clamp(surplus, 0.0, max_charge)
                        target_out_w = 0.0

                    # Bei Defizit (Netzbezug) entladen, wenn SoC > min
                    elif deficit > 80 and soc > soc_min:
                        status = "cover_deficit"
                        rec = REC_DISCHARGE
                        target_mode = "output"
                        target_out_w = _clamp(deficit, 0.0, max_discharge)
                        target_in_w = 0.0

                    else:
                        rec = REC_STANDBY

                # AUTOMATIC: kombiniert (PV + Preis wenn vorhanden)
                else:
                    # 1) PV-Überschuss laden
                    if surplus > 80 and soc < soc_max:
                        status = "pv_surplus"
                        rec = REC_CHARGE
                        target_mode = "input"
                        target_in_w = _clamp(surplus, 0.0, max_charge)
                        target_out_w = 0.0

                    # 2) Preis teuer -> entladen
                    elif has_price and price_now >= price_thr and soc > soc_min:
                        status = "expensive_now"
                        rec = REC_DISCHARGE
                        target_mode = "output"
                        target_out_w = _clamp(deficit, 0.0, max_discharge)
                        target_in_w = 0.0

                    # 3) Wenn bald Peak kommt: SoC nicht weiter sinnlos entladen, eher halten
                    else:
                        rec = REC_STANDBY

            # --------------------------------------------------
            # Freeze: Status/Empfehlung einfrieren (gegen Flackern)
            # Hardware (target_*) NICHT einfrieren => bleibt dynamisch
            # --------------------------------------------------
            now_utc = dt_util.utcnow()
            if freeze_s > 0:
                if self._freeze_until and now_utc < self._freeze_until:
                    status = self._last_status or status
                    rec = self._last_rec or rec
                else:
                    self._freeze_until = now_utc + timedelta(seconds=int(freeze_s))
                    self._last_status = status
                    self._last_rec = rec

            # --------------------------------------------------
            # Safety: keine Entladung unter soc_min
            # --------------------------------------------------
            if target_mode == "output" and soc <= soc_min:
                target_out_w = 0.0
                rec = REC_HOLD
                status = "soc_guard"

            # --------------------------------------------------
            # Apply hardware
            # --------------------------------------------------
            await self._set_ac_mode(target_mode)
            await self._set_input_limit(target_in_w if target_mode == "input" else 0.0)
            await self._set_output_limit(target_out_w if target_mode == "output" else 0.0)

            # --------------------------------------------------
            # Return data for sensors
            # --------------------------------------------------
            return {
                "status": status,
                "recommendation": rec,
                "debug": "OK",
                "details": {
                    "ai_mode": ai_mode,
                    "manual_action": manual_action,
                    "soc": round(soc, 2),
                    "soc_min": soc_min,
                    "soc_max": soc_max,
                    "pv": round(pv, 1),
                    "load": round(load, 1),
                    "surplus": round(surplus, 1),
                    "deficit": round(deficit, 1),
                    "price_now": None if price_now is None else round(float(price_now), 4),
                    "price_threshold": price_thr,
                    "very_expensive_threshold": very_exp,
                    "idx_now": idx_now,
                    "price_analysis": price_info,
                    "set_mode": target_mode,
                    "set_input_w": round(target_in_w, 0),
                    "set_output_w": round(target_out_w, 0),
                    "entities": {
                        "soc": self.entities.soc,
                        "pv": self.entities.pv,
                        "load": self.entities.load,
                        "price_export": self.entities.price_export,
                        "ac_mode": self.entities.ac_mode,
                        "input_limit": self.entities.input_limit,
                        "output_limit": self.entities.output_limit,
                    },
                },
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
