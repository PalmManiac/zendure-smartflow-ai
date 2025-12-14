from __future__ import annotations

DOMAIN = "zendure_smartflow_ai"

# Wir erzeugen in V0.1.0 nur Sensoren (GUI-Steuerung läuft über vorhandene Helper)
PLATFORMS: tuple[str, ...] = ("sensor",)

# Betriebsmodi (werden aus input_select.zendure_betriebsmodus gelesen)
MODE_AUTOMATIC = "Automatik"
MODE_SUMMER = "Sommer"
MODE_WINTER = "Winter"
MODE_MANUAL = "Manuell"

MODES = [MODE_AUTOMATIC, MODE_SUMMER, MODE_WINTER, MODE_MANUAL]

# Recommendation Keys (stabil, werden in Automationen/Logik genutzt)
REC_STANDBY = "standby"
REC_LADEN = "laden"
REC_BILLIG_LADEN = "billig_laden"
REC_KI_LADEN = "ki_laden"
REC_ENTLADEN = "entladen"

# AI-Status Keys (stabil, für Debug/Anzeige)
AI_DATA_PROBLEM = "datenproblem_preisquelle"

AI_NOTLADUNG_AKTIV = "notladung_aktiv"
AI_TEUER_AKKUSCHUTZ = "teuer_jetzt_akkuschutz"
AI_TEUER_ENTLADEN = "teuer_jetzt_entladen"

AI_GUENSTIG_JETZT_LADEN = "guenstig_jetzt_laden"
AI_GUENSTIG_WARTEN = "guenstige_phase_kommt_noch"
AI_GUENSTIG_VERPASST = "guenstigste_phase_verpasst"

AI_PV_UEBERSCHUSS_LADEN = "pv_ueberschuss_laden"
AI_STANDBY = "standby"
AI_MANUELL = "manuell"

# Freeze / Stabilisierung
# Empfehlung darf nur wechseln, wenn:
# - neuer 15-Minuten-Slot ODER
# - Modus geändert ODER
# - Notfall/Schwellenwechsel
FREEZE_MIN_TOL_W = 25.0  # Totzone für Setpoints (verhindert Flattern)
