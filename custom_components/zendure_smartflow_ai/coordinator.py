from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    UPDATE_INTERVAL,

    # config keys
    CONF_SOC_ENTITY,
    CONF_PV_ENTITY,
    CONF_PRICE_EXPORT_ENTITY,
    CONF_PRICE_NOW_ENTITY,
    CONF_AC_MODE_ENTITY,
    CONF_INPUT_LIMIT_ENTITY,
    CONF_OUTPUT_LIMIT_ENTITY,
    CONF_GRID_MODE,
    CONF_GRID_POWER_ENTITY,
    CONF_GRID_IMPORT_ENTITY,
    CONF_GRID_EXPORT_ENTITY,
    GRID_MODE_NONE,
    GRID_MODE_SINGLE,
    GRID_MODE_SPLIT,

    # modes
    AI_MODE_AUTOMATIC,
    AI_MODE_SUMMER,
    AI_MODE_WINTER,
    AI_MODE_MANUAL,
    MANUAL_STANDBY,
    MANUAL_CHARGE,
    MANUAL_DISCHARGE,

    # settings keys
    SETTING_SOC_MIN,
    SETTING_SOC_MAX,
    SETTING_MAX_CHARGE,
    SETTING_MAX_DISCHARGE,
    SETTING_PRICE_THRESHOLD,
    SETTING_VERY_EXPENSIVE_THRESHOLD,
    SETTING_EMERGENCY_SOC,
    SETTING_EMERGENCY_CHARGE,
    SETTING_PROFIT_MARGIN_PCT,

    # defaults
    DEFAULT_SOC_MIN,
    DEFAULT_SOC_MAX,
    DEFAULT_MAX_CHARGE,
    DEFAULT_MAX_DISCHARGE,
    DEFAULT_PRICE_THRESHOLD,
    DEFAULT_VERY_EXPENSIVE_THRESHOLD,
    DEFAULT_EMERGENCY_SOC,
    DEFAULT_EMERGENCY_CHARGE,
    DEFAULT_PROFIT_MARGIN_PCT,

    # statuses
    STATUS_INIT,
    STATUS_OK,
    STATUS_SENSOR_INVALID,
    STATUS_PRICE_INVALID,

    AI_STATUS_STANDBY,
    AI_STATUS_CHARGE_SURPLUS,
    AI_STATUS_COVER_DEFICIT,
    AI_STATUS_EXPENSIVE_DISCHARGE,
    AI_STATUS_VERY_EXPENSIVE_FORCE,
    AI_STATUS_EMERGENCY_CHARGE,
    AI_STATUS_MANUAL,

    RECO_STANDBY,
    RECO_CHARGE,
    RECO_DISCHARGE,
    RECO_EMERGENCY,

    ZENDURE_MODE_INPUT,
    ZENDURE_MODE_OUTPUT,
)

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1

# Anti-Schwingung (Regel-Stabilisierung) – verhindert Oszillation bei Defizitmessung
ANTI_SWING_HOLD_S = 15          # Mindesthaltezeit für einen gesetzten Entlade-Wert
ANTI_SWING_STEP_W = 120         # maximale Änderung pro Update-Zyklus (Rampe)
ANTI_SWING_HYST_W = 100         # Hysterese um kleine Messsprünge zu ignorieren
ANTI_SWING_START_W = 80        # Defizit, ab dem Entladen überhaupt startet
ANTI_SWING_STOP_W = 40          # Defizit, unter dem Entladen beendet werden darf (nach Hold)


@dataclass
class EntityIds:
    soc: str
    pv: str

    price_export: str | None
    price_now: str | None

    grid_mode: str
    grid_power: str | None
    grid_import: str | None
    grid_export: str | None

    ac_mode: str
    input_limit: str
    output_limit: str


def _to_float(val: Any, default: float | None = None) -> float | None:
    try:
        if val is None:
            return default
        s = str(val).replace(",", ".").strip()
        if s.lower() in ("unknown", "unavailable", ""):
            return default
        return float(s)
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Core brain + persistence."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        # coordinator.py – im __init__()
        self.runtime_settings: dict[str, float] = {
            SETTING_SOC_MIN: entry.options.get(SETTING_SOC_MIN, DEFAULT_SOC_MIN),
            SETTING_SOC_MAX: entry.options.get(SETTING_SOC_MAX, DEFAULT_SOC_MAX),
            SETTING_MAX_CHARGE: entry.options.get(SETTING_MAX_CHARGE, DEFAULT_MAX_CHARGE),
            SETTING_MAX_DISCHARGE: entry.options.get(SETTING_MAX_DISCHARGE, DEFAULT_MAX_DISCHARGE),
            SETTING_EMERGENCY_CHARGE: entry.options.get(
                SETTING_EMERGENCY_CHARGE, DEFAULT_EMERGENCY_CHARGE
            ),
            SETTING_EMERGENCY_SOC: entry.options.get(
                SETTING_EMERGENCY_SOC, DEFAULT_EMERGENCY_SOC
            ),
            SETTING_VERY_EXPENSIVE_THRESHOLD: entry.options.get(
                SETTING_VERY_EXPENSIVE_THRESHOLD, DEFAULT_VERY_EXPENSIVE_THRESHOLD
            ),
            SETTING_PROFIT_MARGIN_PCT: entry.options.get(
                SETTING_PROFIT_MARGIN_PCT, DEFAULT_PROFIT_MARGIN_PCT
            ),
        }

        data = entry.data or {}

        self.entities = EntityIds(
            soc=data[CONF_SOC_ENTITY],
            pv=data[CONF_PV_ENTITY],

            price_export=data.get(CONF_PRICE_EXPORT_ENTITY),
            price_now=data.get(CONF_PRICE_NOW_ENTITY),

            grid_mode=data.get(CONF_GRID_MODE, GRID_MODE_SINGLE),
            grid_power=data.get(CONF_GRID_POWER_ENTITY),
            grid_import=data.get(CONF_GRID_IMPORT_ENTITY),
            grid_export=data.get(CONF_GRID_EXPORT_ENTITY),

            ac_mode=data[CONF_AC_MODE_ENTITY],
            input_limit=data[CONF_INPUT_LIMIT_ENTITY],
            output_limit=data[CONF_OUTPUT_LIMIT_ENTITY],
        )

        # runtime selects (persisted)
        self.runtime_mode: dict[str, str] = {
            "ai_mode": AI_MODE_AUTOMATIC,
            "manual_action": MANUAL_STANDBY,
        }

        # persistent analytics + emergency latch
        self._store = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._persist: dict[str, Any] = {
   	    	"runtime_mode": dict(self.runtime_mode),

    		"emergency_active": False,

    		# --- V1.2 planning (inactive) ---
    		"planning_active": False,
    		"planning_target_soc": None,
    		"planning_next_peak": None,   # dict or None
    		"planning_reason": None,

    		# --- anti oscillation ---
    		"last_out_w": 0.0,
    		"last_out_ts": None,
    		"discharge_active_since": None,

    		# analytics
    		"avg_charge_price": None,
    		"charged_kwh": 0.0,
    		"discharged_kwh": 0.0,
    		"profit_eur": 0.0,
    		"last_ts": None,
		}

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def async_shutdown(self) -> None:
        await self._save()

    async def _load(self) -> None:
        try:
            stored = await self._store.async_load()
            if isinstance(stored, dict):
                self._persist.update(stored)
                rm = self._persist.get("runtime_mode")
                if isinstance(rm, dict):
                    self.runtime_mode.update({k: str(v) for k, v in rm.items()})
        except Exception as err:
            _LOGGER.debug("Store load failed: %s", err)

    async def _save(self) -> None:
        try:
            self._persist["runtime_mode"] = dict(self.runtime_mode)
            await self._store.async_save(self._persist)
        except Exception as err:
            _LOGGER.debug("Store save failed: %s", err)

    def _state(self, entity_id: str | None) -> Any:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _attr(self, entity_id: str | None, attr: str) -> Any:
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        return None if st is None else st.attributes.get(attr)

    # --------------------------------------------------
    # price
    # --------------------------------------------------
    def _price_now(self) -> float | None:
        # direct price sensor wins
        if self.entities.price_now:
            return _to_float(self._state(self.entities.price_now), None)

        # export data list
        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list) or not export:
            return None

        now = dt_util.now()
        idx = int((now.hour * 60 + now.minute) // 15)

        try:
            item = export[idx]
            if isinstance(item, dict):
                return _to_float(item.get("price_per_kwh"), None)
        except Exception:
            return None
        return None

    # --------------------------------------------------
    # house load from grid + pv (no helper required)
    # --------------------------------------------------
    def _calc_house_load(self, pv_w: float) -> tuple[float | None, float | None, float | None]:
        """
        Returns: (house_load_w, grid_import_w, grid_export_w)

        Using:
        - single grid_power (+import / -export): load = pv + grid_power
        - split: load = pv + import - export
        - none: load unknown
        """
        mode = self.entities.grid_mode or GRID_MODE_NONE

        if mode == GRID_MODE_SINGLE and self.entities.grid_power:
            gp = _to_float(self._state(self.entities.grid_power), None)
            if gp is None:
                return None, None, None
            imp = max(gp, 0.0)
            exp = max(-gp, 0.0)
            load = max(pv_w + gp, 0.0)
            return load, imp, exp

        if mode == GRID_MODE_SPLIT and self.entities.grid_import and self.entities.grid_export:
            gi = _to_float(self._state(self.entities.grid_import), None)
            ge = _to_float(self._state(self.entities.grid_export), None)
            if gi is None or ge is None:
                return None, None, None
            load = max(pv_w + gi - ge, 0.0)
            return load, max(gi, 0.0), max(ge, 0.0)

        return None, None, None

    # --------------------------------------------------
    # zendure control
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
            {"entity_id": self.entities.input_limit, "value": int(round(float(watts), 0))},
            blocking=False,
        )

    async def _set_output_limit(self, watts: float) -> None:
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self.entities.output_limit, "value": int(round(float(watts), 0))},
            blocking=False,
        )

    # --------------------------------------------------
    # settings (stored in config entry options)
    # --------------------------------------------------
    def _get_setting(self, key: str, default: float) -> float:
        """Read setting from config entry options (single source of truth)."""
        try:
            val = self.entry.options.get(key, default)
            return float(val)
        except Exception:
            return float(default)

    def _smooth_discharge_output(self, target_w: float, deficit_w: float | None, now_dt) -> float:
        """Stabilisiert Entladeleistung gegen Oszillation.

        Hintergrund:
        Der gemessene Netzbezug (Defizit) reagiert verzögert auf das gesetzte Output-Limit.
        Ohne Stabilisierung entsteht ein Regelkreis (z.B. 1200W Defizit -> 1100W Entladung -> 100W Defizit -> 100W Entladung -> 1100W Defizit ...).

        Strategie:
        - Mindesthaltezeit (ANTI_SWING_HOLD_S) für zuletzt gesetzten Wert
        - Hysterese (ANTI_SWING_HYST_W) gegen kleine Schwankungen/Export-Spikes
        - Rampenlimit (ANTI_SWING_STEP_W) pro Update
        - Start/Stop-Schwellen (ANTI_SWING_START_W/STOP_W)
        """
        last_w = float(self._persist.get("last_out_w") or 0.0)
        last_ts = self._persist.get("last_out_ts")
        last_dt = None
        if last_ts:
            try:
                last_dt = dt_util.parse_datetime(last_ts)
            except Exception:
                last_dt = None

        age_s = 1e9
        if last_dt:
            try:
                age_s = max((now_dt - last_dt).total_seconds(), 0.0)
            except Exception:
                age_s = 1e9

        # Wenn Defizit unbekannt ist: innerhalb Hold beibehalten, sonst sanft auf 0.
        if deficit_w is None:
            if age_s < ANTI_SWING_HOLD_S:
                return last_w
            return 0.0

        deficit = max(float(deficit_w), 0.0)

        # Stop-Logik: erst nach Hold wirklich auf 0 gehen (Export-Spikes abfangen)
        if deficit < ANTI_SWING_STOP_W:
            if age_s < ANTI_SWING_HOLD_S and last_w > 0:
                return last_w
            return 0.0

        # Start-Logik: unter Start-Schwelle nicht anlaufen (gegen Rauschen)
        if last_w <= 0.0 and deficit < ANTI_SWING_START_W:
            return 0.0

        # Hysterese: innerhalb +/- HYST um den aktuellen Wert nicht nachregeln
        if last_w > 0.0 and abs(deficit - last_w) < ANTI_SWING_HYST_W:
            return last_w

        # Zielwert: wir wollen i.d.R. Defizit decken, aber stabil (Rampe)
        target = max(float(target_w), 0.0)

        # Innerhalb Hold: nur in Richtung "mehr" reagieren, wenn deutlich größer
        if age_s < ANTI_SWING_HOLD_S and last_w > 0.0 and deficit < last_w:
            # Defizit kleiner als zuletzt: innerhalb Hold nicht sofort runterregeln
            target = max(last_w, target)

        # Rampenlimit pro Update
        delta = target - last_w
        if delta > ANTI_SWING_STEP_W:
            target = last_w + ANTI_SWING_STEP_W
        elif delta < -ANTI_SWING_STEP_W:
            target = last_w - ANTI_SWING_STEP_W

        return max(target, 0.0)
        
	# --------------------------------------------------
    # V1.2 – Preis-Vorplanung (aktiv)
    # --------------------------------------------------
    def _evaluate_price_planning(
        self,
        now_dt,
        soc: float,
        soc_max: float,
        price_now: float | None,
        expensive: float,
        very_expensive: float,
        profit_margin_pct: float,
        max_charge: float,
        surplus_w: float | None,
    ) -> dict[str, Any] | None:
        """
        Preis-Vorplanung (V1.2.0 Basis):

        Idee:
        - Finde die nächste Preisspitze (>= very_expensive ODER >= expensive + Marge)
        - Schaue alle Slots bis dahin an und definiere das "Billigfenster" = günstigste 25%
        - Wenn wir JETZT im Billigfenster sind, laden wir (Netzladung) so stark wie erlaubt,
          bis soc_max erreicht ist.

        Einschränkung:
        - Wir planen nur mit dem Export-Preisarray (price_export:data), da price_now alleine keine Zukunft kennt.
        - Wir planen nur bis zum nächsten Peak innerhalb des heutigen Arrays.
        """

        # Wenn SOC bereits voll (oder drüber) -> nix planen
        if soc >= soc_max:
            return None

        # Wenn PV-Überschuss gerade da ist: PV-Logik soll gewinnen (kein Netzladen "dazwischen")
        if surplus_w is not None and float(surplus_w) > 50.0:
            return None

        # Ohne aktuellen Preis bringt "bin ich im Billigfenster?" nichts
        if price_now is None:
            return None

        # Wir brauchen zukünftige Preise -> nur möglich, wenn price_export vorhanden ist
        if not self.entities.price_export:
            return None

        export = self._attr(self.entities.price_export, "data")
        if not isinstance(export, list) or len(export) < 2:
            return None

        # Index im 15-Minuten Raster (wie in _price_now)
        local_now = dt_util.now()
        idx_now = int((local_now.hour * 60 + local_now.minute) // 15)
        if idx_now < 0 or idx_now >= len(export):
            return None

        # Preise ab "jetzt" bis Ende des Arrays lesen
        future_prices: list[float] = []
        for i in range(idx_now, len(export)):
            item = export[i]
            if isinstance(item, dict):
                p = _to_float(item.get("price_per_kwh"), None)
                if p is not None:
                    future_prices.append(float(p))
                else:
                    # wenn ein Slot kaputt ist -> abbrechen (keine zuverlässige Planung)
                    return None
            else:
                return None

        if len(future_prices) < 4:
            return None

        # Marge berücksichtigen (profit_margin_pct)
        # -> ab wann gilt es als "Peak", der später teuer wird?
        margin = max(float(profit_margin_pct or 0.0), 0.0) / 100.0
        peak_threshold = max(very_expensive, expensive * (1.0 + margin))

        # Nächsten Peak finden (im future_prices-Array ist Index 0 = jetzt)
        peak_rel_idx = None
        peak_price = None
        for j, p in enumerate(future_prices):
            if p >= peak_threshold:
                peak_rel_idx = j
                peak_price = p
                break

        # Kein Peak in Sicht -> keine Vorplanung (sonst würden wir “immer” laden)
        if peak_rel_idx is None or peak_rel_idx < 1:
            return None

        # Fenster bis zum Peak (ohne Peak-Slot selbst)
        pre_peak = future_prices[:peak_rel_idx]
        if len(pre_peak) < 4:
            return None

        # Billigfenster = günstigste 25% vor dem Peak
        sorted_pre = sorted(pre_peak)
        cheap_count = max(int(len(sorted_pre) * 0.25), 1)
        cheap_threshold = sorted_pre[cheap_count - 1]  # Preisgrenze für "Billig"

        # Sind wir gerade "billig genug"?
        if float(price_now) <= float(cheap_threshold):
            # -> jetzt Laden so stark wie möglich
            watts = max(float(max_charge), 0.0)
            return {
                "action": "charge",
                "watts": watts,
                "reason": f"planning_charge_now(price={price_now:.4f}<=cheap_thr={cheap_threshold:.4f}, peak_thr={peak_threshold:.4f})",
                "cheap_threshold": cheap_threshold,
                "peak_threshold": peak_threshold,
                "peak_price": peak_price,
                "peak_in_slots": peak_rel_idx,
            }

        # Optional: Kurz vor Peak (< 1h) auch laden, selbst wenn nicht ganz im Billig-Quartil
        # (damit du "soweit es das Billigfenster zulässt" maximal voll wirst)
        if peak_rel_idx <= 4 and float(price_now) < float(peak_threshold):
            watts = max(float(max_charge), 0.0)
            return {
                "action": "charge",
                "watts": watts,
                "reason": f"planning_last_chance(peak_in_slots={peak_rel_idx}, price={price_now:.4f}<peak_thr={peak_threshold:.4f})",
                "cheap_threshold": cheap_threshold,
                "peak_threshold": peak_threshold,
                "peak_price": peak_price,
                "peak_in_slots": peak_rel_idx,
            }

        return None
        
    # --------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # lazy-load store once
            if self._persist.get("last_ts") is None:
                await self._load()

            now = dt_util.utcnow()

            soc = _to_float(self._state(self.entities.soc), None)
            pv = _to_float(self._state(self.entities.pv), None)

            if soc is None or pv is None:
                return {
                    "status": STATUS_SENSOR_INVALID,
                    "ai_status": AI_STATUS_STANDBY,
                    "recommendation": RECO_STANDBY,
                    "debug": "SENSOR_INVALID",
                    "details": {
                        "soc_raw": self._state(self.entities.soc),
                        "pv_raw": self._state(self.entities.pv),
                    },
                }

            # settings
            soc_min = self._get_setting(SETTING_SOC_MIN, DEFAULT_SOC_MIN)
            soc_max = self._get_setting(SETTING_SOC_MAX, DEFAULT_SOC_MAX)
            max_charge = self._get_setting(SETTING_MAX_CHARGE, DEFAULT_MAX_CHARGE)
            max_discharge = self._get_setting(SETTING_MAX_DISCHARGE, DEFAULT_MAX_DISCHARGE)

            expensive = self._get_setting(SETTING_PRICE_THRESHOLD, DEFAULT_PRICE_THRESHOLD)
            very_expensive = self._get_setting(
                SETTING_VERY_EXPENSIVE_THRESHOLD, DEFAULT_VERY_EXPENSIVE_THRESHOLD
            )

            emergency_soc = self._get_setting(SETTING_EMERGENCY_SOC, DEFAULT_EMERGENCY_SOC)
            emergency_w = self._get_setting(SETTING_EMERGENCY_CHARGE, DEFAULT_EMERGENCY_CHARGE)

            profit_margin_pct = self._get_setting(SETTING_PROFIT_MARGIN_PCT, DEFAULT_PROFIT_MARGIN_PCT)

            # derived grid/house load
            house_load, grid_import, grid_export = self._calc_house_load(pv_w=float(pv))

            # price (optional)
            price_now = self._price_now()

            # PV surplus/deficit
            surplus = None
            deficit = None
            if house_load is not None:
                surplus = max(float(pv) - float(house_load), 0.0)
                deficit = max(float(house_load) - float(pv), 0.0)
            elif grid_import is not None:
                deficit = float(grid_import)

            # --------------------------------------------------
            # ✅ NEW: Emergency latch logics
            # Trigger at emergency_soc, keep active until soc_min reached
            # --------------------------------------------------
            if soc <= emergency_soc:
                self._persist["emergency_active"] = True

            if self._persist.get("emergency_active") and soc >= soc_min:
                # reached safe minimum -> exit emergency
                self._persist["emergency_active"] = False

            # default outputs
            status = STATUS_OK
            ai_status = AI_STATUS_STANDBY
            recommendation = RECO_STANDBY
            ac_mode = ZENDURE_MODE_INPUT
            in_w = 0.0
            out_w = 0.0
            decision_reason = "idle"
            control_layer = "standby"

            ai_mode = self.runtime_mode.get("ai_mode", AI_MODE_AUTOMATIC)
            manual_action = self.runtime_mode.get("manual_action", MANUAL_STANDBY)

            # -----------------------------
            # SAFETY: Emergency charge (latched)
            # -----------------------------
            if self._persist.get("emergency_active"):
                ai_status = AI_STATUS_EMERGENCY_CHARGE
                recommendation = RECO_EMERGENCY
                ac_mode = ZENDURE_MODE_INPUT
                in_w = min(max_charge, max(emergency_w, 0.0))
                out_w = 0.0
                decision_reason = "emergency_latched_charge"
                control_layer = "emergency"

            else:
                # -----------------------------
                # MANUAL mode overrides
                # -----------------------------
                if ai_mode == AI_MODE_MANUAL:
                    ai_status = AI_STATUS_MANUAL
                    decision_reason = "manual_mode"
                    control_layer = "manual"

                    if manual_action == MANUAL_STANDBY:
                        recommendation = RECO_STANDBY
                        ac_mode = ZENDURE_MODE_INPUT
                        in_w = 0.0
                        out_w = 0.0

                    elif manual_action == MANUAL_CHARGE:
                        recommendation = RECO_CHARGE
                        ac_mode = ZENDURE_MODE_INPUT
                        in_w = min(max_charge, max_charge)
                        out_w = 0.0
                        decision_reason = "manual_charge"

                    elif manual_action == MANUAL_DISCHARGE:
                        recommendation = RECO_DISCHARGE
                        ac_mode = ZENDURE_MODE_OUTPUT
                        in_w = 0.0
                        target = deficit if deficit is not None else max_discharge
                        out_w = min(max_discharge, max(target or 0.0, 0.0))
                        decision_reason = "manual_discharge"

                else:
                    decision_reason = "automatic_idle"
                    # --------------------------------------------------
					# V1.2 Preis-Vorplanung – STEP 2 (aktiv)
					# --------------------------------------------------
					planning = self._evaluate_price_planning(
    					now_dt=now,
    					soc=soc,
    					soc_max=soc_max,
    					price_now=price_now,
    					expensive=expensive,
    					very_expensive=very_expensive,
    					profit_margin_pct=profit_margin_pct,
    					max_charge=max_charge,
    					surplus_w=surplus,
					)

					if planning:
                        control_layer = "planning"
    					self._persist["planning_active"] = True
    					self._persist["planning_target_soc"] = soc_max
    					self._persist["planning_next_peak"] = {
        				 	"peak_threshold": planning.get("peak_threshold"),
        				 	"peak_price": planning.get("peak_price"),
        					"peak_in_slots": planning.get("peak_in_slots"),
        					"cheap_threshold": planning.get("cheap_threshold"),
    					}
    					self._persist["planning_reason"] = planning.get("reason")

    					# >>> PLANUNG ÜBERSCHREIBT AUTOMATIK <<<
    					if planning.get("action") == "charge":
        					ai_status = AI_STATUS_CHARGE_SURPLUS
        					recommendation = RECO_CHARGE
        					ac_mode = ZENDURE_MODE_INPUT
        					in_w = min(max_charge, float(planning.get("watts") or max_charge))
        					out_w = 0.0
        					decision_reason = planning.get("reason") or "planning_charge"

					else:
    					self._persist["planning_active"] = False
    					self._persist["planning_target_soc"] = None
    					self._persist["planning_next_peak"] = None
    					self._persist["planning_reason"] = None
                
                else:
                      
                    # -----------------------------
                    # AUTOMATIC / SUMMER / WINTER
                    # -----------------------------
                    is_summer = ai_mode in (AI_MODE_SUMMER,)
                    is_winter = ai_mode in (AI_MODE_WINTER,)
                    is_auto = ai_mode in (AI_MODE_AUTOMATIC,)

                    # --------------------------------------------------
                    # ☀️ SOMMER: Autarkie priorisieren
                    # → Bei Netzbezug immer entladen (preisunabhängig)
                    # --------------------------------------------------
                    if is_summer and deficit is not None and deficit > 0 and soc > soc_min:
                        ai_status = AI_STATUS_COVER_DEFICIT
                        recommendation = RECO_DISCHARGE
                        ac_mode = ZENDURE_MODE_OUTPUT
                        in_w = 0.0
                        out_w = min(max_discharge, float(deficit))
                        decision_reason = "summer_cover_deficit"

                    # 1) PV surplus charge (needs house_load calculation)
                    elif surplus is not None and surplus > 50 and soc < soc_max:
                        ai_status = AI_STATUS_CHARGE_SURPLUS
                        recommendation = RECO_CHARGE
                        ac_mode = ZENDURE_MODE_INPUT
                        in_w = min(max_charge, surplus)
                        out_w = 0.0
                        decision_reason = "pv_surplus_charge"
                        control_layer = "pv"

                    # 2) Price-based discharge
                    if price_now is None:
                        if (is_winter or is_auto) and (deficit is not None and deficit > 0) and soc > soc_min:
                            pass
                        else:
                            status = STATUS_OK
                    else:
                        if price_now >= very_expensive and soc > soc_min and (deficit is not None and deficit > 0):
                            ai_status = AI_STATUS_VERY_EXPENSIVE_FORCE
                            recommendation = RECO_DISCHARGE
                            ac_mode = ZENDURE_MODE_OUTPUT
                            in_w = 0.0
                            out_w = min(max_discharge, float(deficit))
                            decision_reason = "very_expensive_force_discharge"
                            control_layer = "price"

                        elif price_now >= expensive and soc > soc_min and (deficit is not None and deficit > 0):
                            if is_winter or is_auto:
                                ai_status = AI_STATUS_EXPENSIVE_DISCHARGE
                                recommendation = RECO_DISCHARGE
                                ac_mode = ZENDURE_MODE_OUTPUT
                                in_w = 0.0
                                out_w = min(max_discharge, float(deficit))
                                decision_reason = "expensive_discharge"
                                control_layer = "price"
                            else:
                                pass
                        else:
                            if ai_status == AI_STATUS_STANDBY:
                                recommendation = RECO_STANDBY
                                decision_reason = "standby_no_condition_met"

            # -----------------------------
            # Anti-Schwingung: Entladeleistung stabilisieren (nur wenn OUTPUT aktiv)
            # -----------------------------
            if ac_mode == ZENDURE_MODE_OUTPUT:
                out_w = self._smooth_discharge_output(out_w, deficit, now)
                # Persist Setpoint für nächste Iteration
                self._persist["last_out_w"] = float(out_w)
                self._persist["last_out_ts"] = now.isoformat()
            else:
                # Beim Laden/Standby Setpoint zurücksetzen
                self._persist["last_out_w"] = 0.0
                self._persist["last_out_ts"] = now.isoformat()

            # -----------------------------
            # Price invalid status (only if user provided price source but parsing failed)
            # -----------------------------
            if (self.entities.price_now or self.entities.price_export) and price_now is None:
                status = STATUS_PRICE_INVALID

            # -----------------------------
            # Apply hardware setpoints
            # -----------------------------
            if ac_mode == ZENDURE_MODE_OUTPUT:
                in_w = 0.0
            if ac_mode == ZENDURE_MODE_INPUT:
                out_w = 0.0

            await self._set_ac_mode(ac_mode)
            await self._set_input_limit(in_w)
            await self._set_output_limit(out_w)

            # -----------------------------
            # Analytics: avg charge price + profit (approx, based on setpoints)
            # -----------------------------
            last_ts = self._persist.get("last_ts")
            dt_s = None
            if last_ts:
                try:
                    dt_s = max((now - dt_util.parse_datetime(last_ts)).total_seconds(), 0.0)
                except Exception:
                    dt_s = None
            if dt_s is None or dt_s <= 0:
                dt_s = UPDATE_INTERVAL

            charged_kwh = float(self._persist.get("charged_kwh") or 0.0)
            discharged_kwh = float(self._persist.get("discharged_kwh") or 0.0)
            profit_eur = float(self._persist.get("profit_eur") or 0.0)
            avg_charge_price = self._persist.get("avg_charge_price")

            if ac_mode == ZENDURE_MODE_INPUT and in_w > 0:
                e_kwh = (in_w * dt_s) / 3600000.0
                charged_kwh += e_kwh

                if ai_status == AI_STATUS_CHARGE_SURPLUS:
                    c_price = 0.0
                else:
                    c_price = price_now

                if c_price is not None:
                    if avg_charge_price is None:
                        avg_charge_price = float(c_price)
                    else:
                        prev_e = max(charged_kwh - e_kwh, 0.0)
                        avg_charge_price = (
                            (avg_charge_price * prev_e) + (float(c_price) * e_kwh)
                        ) / max(charged_kwh, 1e-9)

            if ac_mode == ZENDURE_MODE_OUTPUT and out_w > 0:
                e_kwh = (out_w * dt_s) / 3600000.0
                discharged_kwh += e_kwh

                if price_now is not None and avg_charge_price is not None:
                    delta = float(price_now) - float(avg_charge_price)
                    if delta > 0:
                        profit_eur += e_kwh * delta

            self._persist["avg_charge_price"] = avg_charge_price
            self._persist["charged_kwh"] = charged_kwh
            self._persist["discharged_kwh"] = discharged_kwh
            self._persist["profit_eur"] = profit_eur
            self._persist["last_ts"] = now.isoformat()

            await self._save()

            details = {
                "ai_mode": ai_mode,
                "manual_action": manual_action,

                "soc": soc,
                "soc_min": soc_min,
                "soc_max": soc_max,

                "pv": pv,
                "house_load": house_load,
                "grid_import": grid_import,
                "grid_export": grid_export,

                "surplus": surplus,
                "deficit": deficit,

                "price_now": price_now,
                "expensive_threshold": expensive,
                "very_expensive_threshold": very_expensive,

                "emergency_soc": emergency_soc,
                "emergency_charge_w": emergency_w,
                "emergency_active": bool(self._persist.get("emergency_active")),

                "max_charge": max_charge,
                "max_discharge": max_discharge,

                "set_mode": ac_mode,
                "set_input_w": int(round(in_w, 0)),
                "set_output_w": int(round(out_w, 0)),

                "avg_charge_price": avg_charge_price,
                "charged_kwh": charged_kwh,
                "discharged_kwh": discharged_kwh,
                "profit_eur": profit_eur,

                "profit_margin_pct": profit_margin_pct,
            }
            
            details["control_layer"] = control_layer

			details["planning"] = {
   			 	"active": bool(self._persist.get("planning_active")),
    			"reason": self._persist.get("planning_reason"),
    			"target_soc": self._persist.get("planning_target_soc"),
    			"next_peak": self._persist.get("planning_next_peak"),
			}

            return {
                "status": status,
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK" if status == STATUS_OK else status.upper(),
                "details": details,
                "decision_reason": decision_reason,
            }

        except Exception as err:
            raise UpdateFailed(str(err)) from err
