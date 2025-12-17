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


# =========================
# Defaults (falls ConfigFlow-Keys fehlen)
# =========================
@dataclass(frozen=True)
class Defaults:
    soc_entity: str = "sensor.solarflow_2400_ac_electric_level"
    pv_entity: str = "sensor.sb2_5_1vl_40_401_pv_power"
    load_entity: str = "sensor.gesamtverbrauch"
    price_now_entity: str = "sensor.paul_schneider_strasse_39_aktueller_strompreis_energie_dashboard"

    # Netz (optional)
    grid_mode: str = "single_sensor"  # single_sensor | split_sensors | none
    grid_power_entity: str | None = None
    grid_import_entity: str | None = None
    grid_export_entity: str | None = None

    # Zendure-Steuerung
    ac_mode_entity: str = "select.solarflow_2400_ac_ac_mode"
    input_limit_entity: str = "number.solarflow_2400_ac_input_limit"
    output_limit_entity: str = "number.solarflow_2400_ac_output_limit"


DEFAULTS = Defaults()


# =========================
# Helper
# =========================
def _f(state: str | None, default: float = 0.0) -> float:
    try:
        if state is None or state in ("unknown", "unavailable"):
            return default
        return float(str(state).replace(",", "."))
    except Exception:
        return default


def _pick(entry: ConfigEntry, *keys: str, default: Any = None) -> Any:
    """
    Liest robust:
    1) entry.options
    2) entry.data
    und unterstützt mehrere mögliche Key-Namen (legacy-safe).
    """
    options = entry.options or {}
    data = entry.data or {}

    for k in keys:
        if k in options and options.get(k) not in (None, ""):
            return options.get(k)
    for k in keys:
        if k in data and data.get(k) not in (None, ""):
            return data.get(k)
    return default


# =========================
# Coordinator
# =========================
class ZendureSmartFlowCoordinator(DataUpdateCoordinator[dict[str, Any]]):

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id

        # ---- Messwerte (robust gegen alte/new Keys) ----
        self.soc_entity = _pick(
            entry,
            "soc_entity", "soc", "soc_id",
            default=DEFAULTS.soc_entity,
        )
        self.pv_entity = _pick(
            entry,
            "pv_entity", "pv", "pv_id",
            default=DEFAULTS.pv_entity,
        )
        self.load_entity = _pick(
            entry,
            "load_entity", "load", "load_id", "house_load_entity",
            default=DEFAULTS.load_entity,
        )

        # aktueller Preis (optional – wir können auch ohne weiterlaufen)
        self.price_now_entity = _pick(
            entry,
            "price_now_entity", "price_entity", "price_now", "price",
            default=DEFAULTS.price_now_entity,
        )

        # ---- Netzsensor-Konfig (Schritt 2) ----
        self.grid_mode = _pick(
            entry,
            "grid_mode",
            default=DEFAULTS.grid_mode,
        )
        self.grid_power_entity = _pick(
            entry,
            "grid_power_entity", "grid_entity", "grid_power",
            default=DEFAULTS.grid_power_entity,
        )
        self.grid_import_entity = _pick(
            entry,
            "grid_import_entity", "import_entity", "grid_import",
            default=DEFAULTS.grid_import_entity,
        )
        self.grid_export_entity = _pick(
            entry,
            "grid_export_entity", "export_entity", "grid_export",
            default=DEFAULTS.grid_export_entity,
        )

        # ---- Zendure Steuerung ----
        self.ac_mode_entity = _pick(
            entry,
            "ac_mode_entity", "ac_mode", "ac_mode_id",
            default=DEFAULTS.ac_mode_entity,
        )
        self.input_limit_entity = _pick(
            entry,
            "input_limit_entity", "input_limit", "input_limit_id",
            default=DEFAULTS.input_limit_entity,
        )
        self.output_limit_entity = _pick(
            entry,
            "output_limit_entity", "output_limit", "output_limit_id",
            default=DEFAULTS.output_limit_entity,
        )

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

        _LOGGER.debug(
            "Zendure SmartFlow AI entities: soc=%s pv=%s load=%s price_now=%s grid_mode=%s grid=%s import=%s export=%s",
            self.soc_entity,
            self.pv_entity,
            self.load_entity,
            self.price_now_entity,
            self.grid_mode,
            self.grid_power_entity,
            self.grid_import_entity,
            self.grid_export_entity,
        )

    # -------------------------
    # State helper
    # -------------------------
    def _state(self, entity_id: str | None) -> str | None:
        if not entity_id:
            return None
        s = self.hass.states.get(entity_id)
        return None if s is None else s.state

    # =========================
    # Netz-Logik (Schritt 2)
    # =========================
    def _calc_grid(self) -> tuple[float, float]:
        """
        Liefert immer:
        - grid_import_w ≥ 0
        - grid_export_w ≥ 0
        Unterstützt:
        - single_sensor: Bezug +, Einspeisung -
        - split_sensors: getrennt
        - none/fallback: aus load-pv berechnet
        """
        mode = (self.grid_mode or "single_sensor").lower()

        if mode == "single_sensor" and self.grid_power_entity:
            v = _f(self._state(self.grid_power_entity))
            if v >= 0:
                return v, 0.0
            return 0.0, abs(v)

        if mode == "split_sensors":
            imp = _f(self._state(self.grid_import_entity))
            exp = _f(self._state(self.grid_export_entity))
            return max(imp, 0.0), max(exp, 0.0)

        # Fallback: aus load/pv
        load = _f(self._state(self.load_entity))
        pv = _f(self._state(self.pv_entity))
        net = load - pv
        return max(net, 0.0), max(-net, 0.0)

    # =========================
    # Update
    # =========================
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            now = dt_util.utcnow()

            soc = _f(self._state(self.soc_entity))
            pv = _f(self._state(self.pv_entity))
            load = _f(self._state(self.load_entity))
            price_now = _f(self._state(self.price_now_entity))

            grid_import, grid_export = self._calc_grid()

            # (Logik kommt im nächsten Schritt – hier nur stabile Datenbasis)
            ai_status = "standby"
            recommendation = "standby"

            # Freeze “neutral” (damit später nicht flackert)
            if self._freeze_until and now < self._freeze_until:
                ai_status = self._last_ai_status or ai_status
                recommendation = self._last_recommendation or recommendation
            else:
                self._freeze_until = now + timedelta(seconds=FREEZE_SECONDS)
                self._last_ai_status = ai_status
                self._last_recommendation = recommendation

            return {
                "ai_status": ai_status,
                "recommendation": recommendation,
                "debug": "OK",
                "details": {
                    "soc": soc,
                    "pv": pv,
                    "load": load,
                    "price_now": price_now,
                    "grid_import_w": round(grid_import, 1),
                    "grid_export_w": round(grid_export, 1),
                    "grid_mode": self.grid_mode,
                },
            }

        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
