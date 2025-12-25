# Zendure SmartFlow AI (V0.8.0)

Diese Custom-Integration für Home Assistant bewertet PV, Hausverbrauch und optional Strompreise
(Tibber Datenexport) und steuert die Zendure SolarFlow AC Hardware automatisch.

## Voraussetzungen
- Home Assistant
- Zendure / SolarFlow Integration mit folgenden Entitäten:
  - AC Mode (Select: Input/Output)
  - Input Limit (Number, W)
  - Output Limit (Number, W)

Optional:
- Tibber „Datenexport für Dashboard-Integrationen“ Sensor (liefert `attributes.data` mit `start_time` + `price_per_kwh`)

## Einrichtung
1. Integration hinzufügen: **Zendure SmartFlow AI**
2. Entitäten auswählen:
   - SoC Sensor (%)
   - PV Sensor (W)
   - Hausverbrauch (W)
   - optional: Tibber Datenexport Sensor
   - Zendure AC Mode + Input Limit + Output Limit

## Bedienung
### AI Modus
- `automatic`: PV-Überschuss laden + bei teuren Preisen entladen (wenn Preisquelle vorhanden)
- `summer`: Autarkie: PV laden, bei Defizit entladen
- `winter`: Preis: Peaks glätten, PV laden
- `manual`: Manuelle Aktion steuert direkt (Standby/Laden/Entladen)

### Parameter
- SoC Min / SoC Max (Standard SoC Max = 100%)
- Max Lade-/Entladeleistung
- Teuer-Schwelle (€/kWh)
- Sehr teuer (€/kWh)

## Hinweis
Diese Integration ersetzt externe Helper/Automationen.
