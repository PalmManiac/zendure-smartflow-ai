# Zendure SmartFlow AI

🇩🇪 **Deutsche Anleitung**  
🇬🇧 **English documentation below**

---

## 🔋 Zendure SmartFlow AI – Intelligente Akku-Steuerung für Home Assistant

**Zendure SmartFlow AI** ist eine vollständig lokal laufende Home-Assistant-Integration zur **intelligenten Steuerung von Zendure SolarFlow-Akkus**.

Sie kombiniert:
- PV-Erzeugung
- Hausverbrauch
- Strompreise
- Benutzer-Limits

zu einer **automatischen, sicheren und wirtschaftlichen Lade- & Entladestrategie**.

👉 Kein Cloud-Zwang  
👉 Keine starren Automationen  
👉 Volle Transparenz & Kontrolle

---

## ✨ Hauptfunktionen

- 🤖 **KI-basierte Lade- & Entladeentscheidung**
- ☀️ **PV-Überschussladen**
- ⚡ **Preisabhängige Entladung**
- 🚨 **Notladefunktion bis SoC-Minimum**
- 🏖️ Sommer- / ❄️ Winter- / ⚙️ Automatik-Modus
- 🕹️ Manueller Modus (Laden / Entladen / Standby)
- 📊 **Ø Ladepreis-Berechnung**
- 💰 **Gewinn- / Ersparnis-Analyse**
- 🏠 Unterstützung für **Single- & Split-Grid-Messung**
- 🔒 **100 % lokal**, keine externen Dienste

---

## 🧰 Voraussetzungen

- Home Assistant **2024.6 oder neuer**
- Zendure SolarFlow (AC-gekoppelt)
- Folgende Sensoren:
  - Akku-SoC (%)
  - PV-Leistung (W)
  - Netzleistung (Single oder Split)
- Optional:
  - Strompreis (z. B. Tibber, Awattar, o. ä.)

---

## 📦 Installation

### 🔹 Manuell (Custom Component)

1. Repository herunterladen oder klonen
2. Ordner kopieren nach: /config/custom_components/zendure_smartflow_ai/
3. Home Assistant neu starten
4. **Einstellungen → Geräte & Dienste → Integration hinzufügen**
5. **Zendure SmartFlow AI** auswählen

> 🔜 HACS-Support folgt nach v1.0.0

---

## ⚙️ Einrichtung

Während der Einrichtung verknüpfst du:
- Akku-SoC-Sensor
- PV-Leistung
- Netzsensoren (Single oder Import/Export)
- Zendure-Steuerentitäten (AC-Modus, Lade- & Entlade-Limit)

### Netz-Modi
- **Single**: ein Sensor (+Import / −Export)
- **Split**: getrennte Import- & Export-Sensoren

---

## 🎛️ Steuerelemente (Number & Select Entities)

### Betriebsmodi
- **Automatik** – intelligenter Hybridbetrieb
- **Sommer** – Fokus PV-Laden, Entladen nur bei sehr teuer
- **Winter** – preisorientierte Entladung
- **Manuell** – vollständige Kontrolle

### Manuelle Aktion
- Standby
- Laden
- Entladen

### Grenzwerte & Limits
- **SoC Minimum** – Untergrenze für Entladung
- **SoC Maximum** – Obergrenze für Ladung
- **Max. Ladeleistung**
- **Max. Entladeleistung**
- **Notladung ab SoC**
- **Notladeleistung**
- **Sehr-Teuer-Schwelle**
- **Gewinnmarge (%)**

---

## 🚨 Notladefunktion (wichtig!)

Die Notladefunktion schützt den Akku vor kritischer Tiefentladung.

**Funktionsweise:**
- Aktivierung bei `SoC ≤ Notladung ab SoC`
- Akku wird **zwangsweise geladen**
- Ladevorgang endet **erst bei Erreichen des SoC-Minimums**
- Danach automatische Rückkehr in den Normalbetrieb

✔ Sicherheitspriorität  
✔ Kein „Hängenbleiben“  
✔ Keine Endlosschleifen

---

## 🧠 KI-Logik (vereinfacht erklärt)

**Prioritäten:**
1. Sicherheit (Notladung)
2. PV-Überschuss nutzen
3. Wirtschaftlichkeit (Strompreis)
4. Benutzer-Limits

### Laden
- PV-Überschuss → Akku
- Günstiger Strom → optional

### Entladen
- Hoher Strompreis
- Innerhalb der SoC-Grenzen
- Abhängig vom Modus

---

## 📊 Sensoren & Status

- **Systemstatus** – OK / Sensorfehler / Preisfehler
- **KI-Status** – aktueller Entscheidungszustand
- **KI-Empfehlung** – Laden / Entladen / Standby
- **Ø Ladepreis Akku**
- **Gewinn / Ersparnis (gesamt)**

---

## ❓ FAQ

**Warum passiert gerade nichts?**  
→ Kein PV-Überschuss, Preis nicht attraktiv oder SoC-Limits erreicht.

**Was passiert ohne Strompreis?**  
→ PV-Logik funktioniert weiterhin, Preislogik wird übersprungen.

**Warum wird nicht entladen?**  
→ Schutz durch SoC-Minimum oder Modus-Logik.

---

## 🛣️ Roadmap

- Weitere Optimierungen der Preislogik
- Prognose-Einbindung
- Dashboard-Beispiele
- HACS-Integration (inkl. Logo)

---

## 🤝 Mitwirken

- Issues & Feature-Wünsche willkommen
- Pull Requests gern gesehen
- Ziel: **stabile, transparente & sichere Akku-Steuerung**

---

---

# Zendure SmartFlow AI (English)

## 🔋 Intelligent Battery Control for Home Assistant

**Zendure SmartFlow AI** is a fully local Home Assistant integration for **intelligent control of Zendure SolarFlow batteries**.

It combines:
- PV production
- Household consumption
- Electricity prices
- User-defined limits

into a **safe, efficient and automated charging strategy**.

---

## ✨ Features

- 🤖 AI-based charge & discharge decisions
- ☀️ PV surplus charging
- ⚡ Price-based discharging
- 🚨 Emergency charging up to SoC minimum
- Automatic / Summer / Winter / Manual modes
- 📊 Average charge price calculation
- 💰 Profit & savings analytics
- 🏠 Single & split grid support
- 🔒 100 % local operation

---

## 🧰 Requirements

- Home Assistant **2024.6+**
- Zendure SolarFlow system
- Sensors:
  - Battery SoC
  - PV power
  - Grid power (single or split)
- Optional electricity price sensor

---

## 📦 Installation

Manual installation via `custom_components`  
(HACS support planned)

---

## ⚙️ Configuration

Link:
- Battery sensors
- PV sensor
- Grid sensors
- Zendure control entities

---

## 🚨 Emergency Charging Logic

- Triggered when SoC ≤ emergency threshold
- Charges battery until **SoC minimum is reached**
- Automatically deactivates afterwards

---

## 🧠 Control Logic

Priority:
1. Safety
2. PV surplus
3. Price optimization
4. User limits

---

## 📊 Sensors

- System status
- AI status
- Recommendation
- Average charge price
- Total profit / savings

---

## 🛣️ Roadmap

- Further AI improvements
- Forecast integration
- HACS release

---

## 🤝 Contributing

Feedback, issues and pull requests are welcome.
