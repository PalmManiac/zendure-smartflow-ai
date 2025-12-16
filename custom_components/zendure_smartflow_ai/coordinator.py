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
FREEZE_SECONDS = 120          # Recommendation-Freeze (wird bei "teuer_jetzt" nicht blockierend angewendet)

# =========================
# Entity IDs (werden bei Installation pro User gespeichert)
# =========================
@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str

    # Preisquellen (wichtig!)
    price_export: str          # Tibber "Datenexport für Dashboard-Integrationen"
    price_now_fallback: str    # optionaler Fallback, falls Export fehlt (muss numeric sein)

    # interne Regler (kommen aus deiner Integration als number/select)
    soc_min: str
    soc_max: str
    expensive_threshold: str
    max_charge: str
    max_discharge: str

    # Zendure Steuer-Entitäten
    ac_mode: str
    input_limit: str
    output_limit: str


DEFAULT_ENTITY_IDS = EntityIds(
    soc="sensor.solarflow_2400_ac_electric_level",
    pv="sensor.sb2_5_1vl_40_401_pv_power",
    load="sensor.gesamtverbrauch",

    # WICHTIG: Export ist die echte Preisquelle (State ist ready/pending, Preis steckt in attributes.data[])
    price_export="sensor.paul_schneider_strasse_39_diagramm_datenexport",
    # optionaler Fallback (wenn vorhanden und numeric). Kann auch irgendein Preis-Sensor sein.
    price_now_fallback="sensor.paul_schneider_strasse_39_aktueller_strompreis_energie_dashboard",

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
def _to_float(v: Any) -> float | None:
    """Robustes float parsing. Gibt None zurück bei unknown/unavailable/nicht numeric."""
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("unknown", "unavailable", "none", ""):
        return None
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return None


# =========================
# Coordinator
# =========================
class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        # Entity IDs aus ConfigEntry lesen (wichtig: bei deinem Bekannten andere Namen!)
        data = entry.data or {}
        self.entities = EntityIds(
            soc=data.get("soc_entity", DEFAULT_ENTITY_IDS.soc),
            pv=data.get("pv_entity", DEFAULT_ENTITY_IDS.pv),
            load=data.get("load_entity", DEFAULT_ENTITY_IDS.load),

            price_export=data.get("price_export_entity", DEFAULT_ENTITY_IDS.price_export),
            price_now_fallback=data.get("price_now_entity", DEFAULT_ENTITY_IDS.price_now_fallback),

            soc_min=data.get("soc_min_entity", DEFAULT_ENTITY_IDS.soc_min),
            soc_max=data.get("soc_max_entity", DEFAULT_ENTITY_IDS.soc_max),
            expensive_threshold=data.get("expensive_threshold_entity", DEFAULT_ENTITY_IDS.expensive_threshold),
            max_charge=data.get("max_charge_entity", DEFAULT_ENTITY_IDS.max_charge),
            max_discharge=data.get("max_discharge_entity", DEFAULT_ENTITY_IDS.max_discharge),

            ac_mode=data.get("ac_mode_entity", DEFAULT_ENTITY_IDS.ac_mode),
            input_limit=data.get("input_limit_entity", DEFAULT_ENTITY_IDS.input_limit),
            output_limit=data.get("output_limit_entity", DEFAULT_ENTITY_IDS.output_limit),
        )

        # Freeze
        self._freeze_until: datetime | None = None
        self._last_recommendation: str | None = None
        self._last_ai_status: str | None = None

        # Anti-Flattern / Service-Spam
        self._last_set_mode: str | None = None
        self._last_set_in: float | None = None
        self._last_set_out: float | None = None

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
        if s is None:
            return None
        return s.attributes.get(attr)

    # -------------------------
    # Preis aus Export berechnen
    # -------------------------
    def _extract_prices_from_export(self) -> tuple[list[float], str | None]:
        """
        Export-Sensor:
          attributes.data = [{start_time:..., price_per_kwh: 0.287}, ...]
        State ist meist ready/pending und NICHT der Preis.
        """
        export = self._attr(self.entities.price_export, "data")
        if not export:
            return [], "EXPORT_EMPTY"

        prices: list[float] = []
        try:
            for row in export:
                p = _to_float(row.get("price_per_kwh"))
                if p is None:
                    # überspringen, aber nicht crashen
                    continue
                prices.append(p)
        except Exception:
            return [], "EXPORT_PARSE_ERROR"

        if not prices:
            return [], "EXPORT_NO_NUMERIC"
        return prices, None

    def _idx_now_15min_local(self) -> int:
        """Index ab lokaler Mitternacht (Export startet 00:00 Lokalzeit)."""
        now_local = dt_util.now()
        minutes = (now_local.hour * 60) + now_local.minute
        return int(minutes // 15)

    def _price_now_from_export(self, prices_all: list[float]) -> tuple[float | None, int | None]:
        """Preis im aktuellen Slot aus Export (lokale Zeit)."""
        if not prices_all:
            return None, None
        idx = self._idx_now_15min_local()
        if idx < 0 or idx >= len(prices_all):
            return None, idx
        return prices_all[idx], idx

    # -------------------------
    # Hardware calls (mit Anti-Spam)
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
            {"entity_id": self.entities.input_limit, "value": float(round(watts, 0))},
            blocking=False,
        )

    async def _set_output(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": float(round(watts, 0))},
            blocking=False,
        )

    async def _apply_hw(self, mode: str, in_w: float, out_w: float) -> None:
        """
        Nur anwenden, wenn sich etwas "wirklich" geändert hat.
        -> verhindert Flackern und dass dein manueller Test sofort wieder überschrieben wird,
           wenn sich gar kein Sollwert ändert.
        """
        def changed(prev: float | None, new: float, tol: float = 25.0) -> bool:
            if prev is None:
                return True
            return abs(prev - new) > tol

        # Mode
        if mode != self._last_set_mode:
            await self._set_ac_mode(mode)
            self._last_set_mode = mode

        # Limits
        if changed(self._last_set_in, in_w):
            await self._set_input(in_w)
            self._last_set_in = in_w

        if changed(self._last_set_out, out_w):
            await self._set_output(out_w)
            self._last_set_out = out_w

    # =========================
    # Main update
    # =========================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now_utc = dt_util.utcnow()

            # --- Basiswerte ---
            soc = _to_float(self._state(self.entities.soc))
            pv = _to_float(self._state(self.entities.pv)) or 0.0
            load = _to_float(self._state(self.entities.load)) or 0.0

            # Regler
            soc_min = _to_float(self._state(self.entities.soc_min))
            soc_max = _to_float(self._state(self.entities.soc_max))
            expensive_fixed = _to_float(self._state(self.entities.expensive_threshold))
            max_charge = _to_float(self._state(self.entities.max_charge))
            max_discharge = _to_float(self._state(self.entities.max_discharge))

            # Defaults, falls jemand frisch installiert
            soc_min = soc_min if soc_min is not None else 12.0
            soc_max = soc_max if soc_max is not None else 95.0
            expensive_fixed = expensive_fixed if expensive_fixed is not None else 0.35
            max_charge = max_charge if max_charge is not None else 2000.0
            max_discharge = max_discharge if max_discharge is not None else 700.0

            # SoC muss valide sein, sonst keine Steuerung
            if soc is None:
                return {
                    "ai_status": "datenproblem_soc",
                    "recommendation": "standby",
                    "debug": "SOC_INVALID",
                    "details": {
                        "soc_raw": self._state(self.entities.soc),
                    },
                }

            # --- Preise: primär aus Export ---
            prices_all, export_err = self._extract_prices_from_export()
            price_now, idx_now = self._price_now_from_export(prices_all)

            # Fallback: nur wenn Export nicht nutzbar ODER aktueller Slot nicht erreichbar
            if price_now is None:
                fallback = _to_float(self._state(self.entities.price_now_fallback))
                if fallback is not None:
                    price_now = fallback

            # Wenn immer noch kein Preis -> standby (keine dummen Aktionen)
            if price_now is None:
                return {
                    "ai_status": "datenproblem_preisquelle",
                    "recommendation": "standby",
                    "debug": export_err or "PRICE_INVALID",
                    "details": {
                        "price_export_entity": self.entities.price_export,
                        "price_now_entity": self.entities.price_now_fallback,
                        "price_now_raw": self._state(self.entities.price_now_fallback),
                        "export_state": self._state(self.entities.price_export),
                        "idx_now": idx_now,
                        "prices_len": len(prices_all),
                    },
                }

            # Zukunftsliste (ab jetzt)
            future = []
            if prices_all and idx_now is not None and 0 <= idx_now < len(prices_all):
                future = prices_all[idx_now:]
            else:
                future = []

            # Dynamische Schwelle (optional) + feste Schwelle
            if future:
                minp = min(future)
                maxp = max(future)
                avgp = sum(future) / len(future)
                span = maxp - minp
                expensive_dyn = avgp + span * 0.25
                expensive = max(expensive_fixed, expensive_dyn)
            else:
                minp = price_now
                maxp = price_now
                avgp = price_now
                span = 0.0
                expensive_dyn = expensive_fixed
                expensive = expensive_fixed

            # PV Überschuss
            surplus = max(pv - load, 0.0)

            # Grenzen
            soc_notfall = max(soc_min - 4.0, 5.0)

            # =========================
            # Entscheidungslogik (Core)
            # =========================
            ai_status = "standby"
            recommendation = "standby"

            ac_mode = "input"
            in_w = 0.0
            out_w = 0.0

            # 1) TEUER -> ENTLADE (wenn SoC > Reserve)
            #    (Das ist genau der Teil, der bei dir wegen price_now=0 NIE getriggert hat.)
            if price_now >= expensive:
                if soc <= soc_min:
                    ai_status = "teuer_akkuschutz"
                    recommendation = "standby"
                    ac_mode = "input"
                    in_w = 0.0
                    out_w = 0.0
                else:
                    ai_status = "teuer_jetzt"
                    recommendation = "entladen"
                    ac_mode = "output"
                    need = max(load - pv, 0.0)
                    out_w = min(max_discharge, need)
                    in_w = 0.0

            # 2) NOTFALL (nur wenn wirklich tief)
            elif soc <= soc_notfall and soc < soc_max:
                ai_status = "notladung"
                recommendation = "billig_laden"
                ac_mode = "input"
                in_w = min(max_charge, 300.0)
                out_w = 0.0
                # Notfall soll Freeze NICHT konservieren
                self._freeze_until = None

            # 3) PV-Überschuss
            elif surplus > 80 and soc < soc_max:
                ai_status = "pv_laden"
                recommendation = "laden"
                ac_mode = "input"
                in_w = min(max_charge, surplus)
                out_w = 0.0

            # else standby bleibt

            # =========================
            # Recommendation Freeze
            # =========================
            # WICHTIG: "teuer_jetzt" darf NICHT durch Freeze weggedrückt werden,
            # sonst stehst du wieder bei 0.37€ auf standby.
            freeze_blockable = ai_status not in ("teuer_jetzt", "teuer_akkuschutz", "notladung")

            if freeze_blockable and self._freeze_until and now_utc < self._freeze_until:
                ai_status = self._last_ai_status or ai_status
                recommendation = self._last_recommendation or recommendation
            else:
                self._freeze_until = now_utc + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation

            # =========================
            # Hardware anwenden
            # =========================
            await self._apply_hw(ac_mode, in_w, out_w)

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "price_now": round(price_now, 4),
                    "expensive_threshold_fixed": round(expensive_fixed, 4),
                    "expensive_threshold_dynamic": round(expensive_dyn, 4),
                    "expensive_threshold_effective": round(expensive, 4),
                    "idx_now": idx_now,
                    "future_len": len(future),
                    "min_price_future": round(minp, 4),
                    "max_price_future": round(maxp, 4),
                    "avg_price_future": round(avgp, 4),
                    "soc": round(soc, 2),
                    "soc_min": round(soc_min, 2),
                    "soc_max": round(soc_max, 2),
                    "soc_notfall": round(soc_notfall, 2),
                    "pv": round(pv, 1),
                    "load": round(load, 1),
                    "surplus": round(surplus, 1),
                    "max_charge": round(max_charge, 0),
                    "max_discharge": round(max_discharge, 0),
                    "set_mode": ac_mode,
                    "set_input_w": round(in_w, 0),
                    "set_output_w": round(out_w, 0),
                    "freeze_until": self._freeze_until.isoformat() if self._freeze_until else None,
                    "export_state": self._state(self.entities.price_export),
                    "export_err": export_err,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
