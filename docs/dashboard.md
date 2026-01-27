## Dashboard & Steuerung

### Betriebsmodi

#### 🔹 Automatik (empfohlen)

- PV-Überschuss wird genutzt
- Preis-Vorplanung aktiv
- Entladung bei teurem Strom
- Sehr teure Preise haben immer Vorrang

---

#### 🔹 Sommer

- Fokus auf Autarkie
- Akku deckt Hauslast bei Defizit
- Keine Preis-Vorplanung
- Sehr teure Preise haben weiterhin Vorrang

---

#### 🔹 Winter

- Fokus auf Kostenersparnis
- Frühere Entladung bei teurem Strom
- Preis-Vorplanung aktiv

---

#### 🔹 Manuell

- Keine KI-Eingriffe
- Laden / Entladen / Standby manuell
- Ideal für Tests und Sonderfälle

---

### Wichtiger Hinweis zu Sensoren

Sensoren wie **„Startzeit nächste Aktion“** oder **„Zeitstempel“** können korrekt auf **`unknown`** stehen.

Das bedeutet **keinen Fehler**, sondern:
- aktuell ist **keine Aktion notwendig**
- oder es existiert **keine wirtschaftlich sinnvolle Planung**

```yaml
title: Zendure SmartFlow AI
views:
  - title: Übersicht
    path: smartflow_ai
    icon: mdi:robot
    cards:
      - type: entities
        title: Status & Empfehlung
        entities:
          - sensor.zendure_smartflow_ai_status
          - sensor.zendure_smartflow_ai_ai_status
          - sensor.zendure_smartflow_ai_steuerungsempfehlung
          - sensor.zendure_smartflow_ai_ai_debug

      - type: entities
        title: AI Steuerung
        entities:
          - select.zendure_smartflow_ai_ai_modus
          - select.zendure_smartflow_ai_manuelle_aktion

      - type: entities
        title: Parameter
        entities:
          - number.zendure_smartflow_ai_soc_min
          - number.zendure_smartflow_ai_soc_max
          - number.zendure_smartflow_ai_max_ladeleistung
          - number.zendure_smartflow_ai_max_entladeleistung
          - number.zendure_smartflow_ai_teuer_schwelle
          - number.zendure_smartflow_ai_sehr_teuer
		  
```