from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .ai_logic import calculate_ai_state
from .constants import (
    DEFAULT_SOC_MAX,
    DEFAULT_SOC_MIN,
    MODE_AUTOMATIC,
    OPT_MODE,
    OPT_SOC_MAX,
    OPT_SOC_MIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityIds:
    soc: str
    pv: str
    load: str
    price_now: str
    price_export: str
    expensive_threshold: str


DEFAULT_ENTITY_IDS = EntityIds(
    soc="sensor.solarflow_2400_ac_electric_level",
    pv="sensor.sb2_5_1vl_40_401_pv_power",
    load="sensor.gesamtverbrauch",
    price_now="sensor.paul_schneider_strasse_39_aktueller_strompreis_energie_dashboard",
    price_export="sensor.paul_schneider_strasse_39_diagramm_datenexport",
    expensive_threshold="input_number.zendure_schwelle_teuer",
)


def _f(state: str | None, default: float = 0.0) -> float:
    try:
        if state is None:
            return default
        return float(str(state).replace(",", "."))
    except Exception:
        return default


class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator = Daten holen + Entscheidung. (Option A: KEINE aktive Steuerung)"""

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
            expensive_threshold=data.get("expensive_threshold_entity", DEFAULT_ENTITY_IDS.expensive_threshold),
        )

        super().__init__(
            hass,
            _LOGGER,
            name="Zendure SmartFlow AI",
            update_interval=timedelta(seconds=10),
        )

    # ---------- Options (persistente Werte) ----------
    def get_option_float(self, key: str, fallback: float) -> float:
        val = (self.entry.options or {}).get(key)
        if val is None:
            return fallback
        try:
            return float(val)
        except Exception:
            return fallback

    def get_option_str(self, key: str, fallback: str) -> str:
        val = (self.entry.options or {}).get(key)
        return fallback if val is None else str(val)

    async def set_option(self, key: str, value: Any) -> None:
        options = dict(self.entry.options or {})
        options[key] = value
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        await self.async_request_refresh()

    # ---------- HA State Helper ----------
    def _get_state(self, entity_id: str) -> str | None:
        st = self.hass.states.get(entity_id)
        return None if st is None else st.state

    def _get_attr(self, entity_id: str, attr: str) -> Any:
        st = self.hass.states.get(entity_id)
        if st is None:
            return None
        return st.attributes.get(attr)

    # ---------- Preise ----------
    def _extract_prices(self) -> list[float]:
        """
        Tibber Datenexport:
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
        now = dt_util.now()
        minutes = now.hour * 60 + now.minute
        return int(minutes // 15)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            # --- Livewerte ---
            soc = _f(self._get_state(self.entities.soc), 0.0)
            pv = _f(self._get_state(self.entities.pv), 0.0)
            load = _f(self._get_state(self.entities.load), 0.0)
            price_now = _f(self._get_state(self.entities.price_now), 0.0)

            expensive_threshold_fixed = _f(self._get_state(self.entities.expensive_threshold), 0.35)

            # --- Optionen (Integration-eigene Werte) ---
            # Fallback: wenn keine Optionen gesetzt sind, nutzen wir "deine alten Helper" NICHT hier,
            # sondern Defaultwerte. (Damit keine Doppel-Entitäten/Flattern entstehen.)
            soc_min = self.get_option_float(OPT_SOC_MIN, DEFAULT_SOC_MIN)
            soc_max = self.get_option_float(OPT_SOC_MAX, DEFAULT_SOC_MAX)
            mode = self.get_option_str(OPT_MODE, MODE_AUTOMATIC)

            # --- Preisreihe / Future ---
            prices_all = self._extract_prices()
            idx = self._idx_now_15min()
            future = prices_all[idx:] if idx < len(prices_all) else []

            ai_result = calculate_ai_state(
                soc=soc,
                soc_min=soc_min,
                soc_max=soc_max,
                pv=pv,
                load=load,
                price_now=price_now,
                future_prices=future,
                expensive_threshold_fixed=expensive_threshold_fixed,
                mode=mode,
            )

            # Option A: KEINE aktive Steuerung (keine Services!)
            return {
                "ai_status": ai_result.get("ai_status", "standby"),
                "recommendation": ai_result.get("recommendation", "standby"),
                "debug": ai_result.get("debug", "OK"),
                "details": ai_result.get("details", {}),
                "price_now": ai_result.get("price_now"),
                "expensive_threshold": ai_result.get("expensive_threshold"),
                "mode": mode,
                "soc_min": soc_min,
                "soc_max": soc_max,
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
