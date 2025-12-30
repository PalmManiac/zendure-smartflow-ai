# Zendure SmartFlow AI

**Intelligente, preis- und PV-basierte Steuerung für Zendure SolarFlow Systeme in Home Assistant**

---

## 🇩🇪 Deutsch

### Überblick

**Zendure SmartFlow AI** ist eine Home-Assistant-Integration zur intelligenten Steuerung von Zendure-SolarFlow-Systemen.  
Sie kombiniert **PV-Erzeugung**, **Hausverbrauch**, **Batterie-SoC** und **optionale Strompreise**, um Lade- und Entladeentscheidungen automatisch und sicher zu treffen.

Ziel ist **nicht** maximale Aktivität, sondern **optimales Verhalten**:
- Laden, wenn es sinnvoll ist
- Entladen, wenn es wirtschaftlich ist
- Stillstand, wenn nichts gewonnen wird

---

## Warum diese Integration?

Viele bestehende Lösungen arbeiten mit:
- starren Zeitplänen
- festen Preisgrenzen
- simplen Wenn-Dann-Regeln

**Zendure SmartFlow AI** verfolgt einen anderen Ansatz:

> **Kontext statt Regeln.**

Die Entscheidung basiert immer auf der aktuellen Gesamtsituation:
- Wie viel PV-Leistung steht zur Verfügung?
- Wie hoch ist die Hauslast?
- Wie voll ist der Akku?
- Ist Strom gerade teuer – oder sogar sehr teuer?

---

## Grundprinzip (die „KI“)

Die Integration bewertet zyklisch:

- **PV-Leistung**
- **Hausverbrauch**
- **Netzbezug / Einspeisung**
- **Batterie-SoC**
- **aktueller Strompreis (optional)**

Daraus ergeben sich drei mögliche Aktionen:
- 🔌 **Laden**
- 🔋 **Entladen**
- ⏸️ **Nichts tun**

Die KI ist bewusst **konservativ**:
- Kein unnötiges Entladen
- Kein sinnloses Laden
- Sicherheit geht immer vor Optimierung

---

## Betriebsmodi

### 🔹 Automatik (empfohlen)
Der Standardmodus.

- Lädt bei PV-Überschuss
- Entlädt bei teurem Strom
- Kombiniert Sommer- und Winterlogik
- Optimal für 95 % aller Nutzer

---

### 🔹 Sommer
PV-zentriert.

- Fokus auf Eigenverbrauch
- Entladung **nur bei sehr teurem Strom**
- Ideal bei hoher PV-Leistung

---

### 🔹 Winter
Preisorientiert.

- Aktive Nutzung des Akkus zur Kostenreduktion
- Entlädt bereits bei „teurem“ Strom
- Geeignet bei geringer oder keiner PV-Erzeugung

---

### 🔹 Manuell
Volle Kontrolle durch den Nutzer.

- KI greift nicht ein
- Laden / Entladen / Standby per Auswahl
- Ideal für Tests oder Sonderfälle

---

## Sicherheitsmechanismen (sehr wichtig)

Die Integration enthält mehrere Schutzebenen:

### SoC Minimum
- Unterhalb dieses Wertes wird **nicht entladen**
- Schützt die Batterie langfristig

### SoC Maximum
- Oberhalb dieses Wertes wird **nicht weiter geladen**

### Notladung
- Aktiviert bei kritischem Akkustand
- Übersteuert alle anderen Logiken

---

## Notladefunktion – im Detail

Die Notladung arbeitet mit **zwei Schwellen**:

### 1️⃣ „Notladung ab SoC“
- Ab diesem Wert wird die Notladung **aktiviert**
- Beispiel: 8 %

### 2️⃣ SoC Minimum
- Zielwert der Notladung
- Beispiel: 12 %

👉 Ergebnis:
- Der Akku wird **bis zum SoC Minimum geladen**
- Danach wird die Notladung automatisch beendet
- Die normale KI übernimmt wieder

**Warum so?**
- Verhindert Tiefentladung
- Stellt einen sicheren Betriebszustand wieder her
- Kein „Hängenbleiben“ in der Notladung

---

## Entitäten in Home Assistant

### Select-Entitäten
- Betriebsmodus
- Manuelle Aktion

### Number-Entitäten
- SoC Minimum
- SoC Maximum
- Maximale Ladeleistung
- Maximale Entladeleistung
- Notladeleistung
- Notladung ab SoC
- Sehr-Teuer-Schwelle
- Gewinnmarge

### Sensoren
- Systemstatus
- KI-Status
- KI-Empfehlung
- Hauslast
- Aktueller Strompreis
- Ø Ladepreis Akku
- Gewinn / Ersparnis (gesamt)

---

## Typische Szenarien

### ☀️ Viel PV, wenig Verbrauch
→ Akku lädt mit Überschuss

### 🌙 Abends, hoher Strompreis
→ Akku entlädt zur Kostenvermeidung

### ❄️ Winter ohne PV
→ Akku wird preisabhängig genutzt

### ⚠️ Akku fast leer
→ Notladung greift automatisch

---

## Voraussetzungen

- Home Assistant (aktuelle Version)
- Zendure SolarFlow System
- Sensoren für:
  - Batterie-SoC
  - PV-Leistung
- Optional:
  - Strompreis-Sensor (z. B. Tibber)

---

## Installation

### Manuell
1. Repository herunterladen
2. Ordner `zendure_smartflow_ai` nach  
   `/config/custom_components/` kopieren
3. Home Assistant neu starten
4. Integration hinzufügen

### HACS
> Wird mit Version 1.x offiziell unterstützt

---

## Bekannte Einschränkungen

- Select-Status-Texte aktuell Englisch
- Strompreis-Logik abhängig vom Sensorformat

Diese Punkte werden in zukünftigen Versionen verbessert.

---

## Support & Mitwirkung

- Bugs & Feature-Wünsche bitte über GitHub Issues
- Pull Requests willkommen
- Diese Integration ist ein Community-Projekt

---

---

## 🇬🇧 English

### Overview

**Zendure SmartFlow AI** is a Home Assistant integration for intelligent control of Zendure SolarFlow systems.  
It combines **PV production**, **household load**, **battery SoC**, and **optional electricity prices** to make smart charging and discharging decisions.

The goal is **not maximum activity**, but **optimal behavior**:
- Charge when it makes sense
- Discharge when it is economically beneficial
- Stay idle when nothing is gained

---

## Why this integration?

Many existing solutions rely on:
- fixed schedules
- static price thresholds
- simple if-then rules

**Zendure SmartFlow AI** follows a different philosophy:

> **Context instead of rules.**

Decisions are always based on the complete situation:
- Available PV power
- Current household consumption
- Battery state of charge
- Current electricity price

---

## Core concept

The integration continuously evaluates:

- PV power
- House load
- Grid import / export
- Battery SoC
- Current electricity price (optional)

Possible outcomes:
- 🔌 **Charge**
- 🔋 **Discharge**
- ⏸️ **Standby**

The logic is intentionally **conservative**:
- No unnecessary discharging
- No pointless charging
- Safety always comes first

---

## Operating modes

### 🔹 Automatic (recommended)
Default mode.

- Charges with PV surplus
- Discharges when electricity is expensive
- Hybrid summer/winter behavior
- Best choice for most users

---

### 🔹 Summer
PV-focused.

- Maximizes self-consumption
- Discharges **only at very high prices**
- Ideal for strong PV systems

---

### 🔹 Winter
Price-driven.

- Uses the battery actively to reduce costs
- Discharges already at “expensive” prices
- Suitable for low or no PV production

---

### 🔹 Manual
Full user control.

- AI is disabled
- Manual charge / discharge / standby
- Useful for testing or special situations

---

## Safety mechanisms

### Minimum SoC
- Battery will not discharge below this value

### Maximum SoC
- Charging stops above this level

### Emergency charging
- Activated at critical battery levels
- Overrides all other logic

---

## Emergency charging explained

Two thresholds are used:

1️⃣ **Emergency start SoC**  
2️⃣ **Minimum SoC (target)**

The battery is charged **up to the minimum SoC**,  
then emergency mode automatically ends.

This ensures:
- Battery protection
- Safe operating state
- No permanent emergency mode

---

## Entities

- Selects: operating mode, manual action
- Numbers: SoC limits, power limits, thresholds
- Sensors: status, recommendations, prices, statistics

---

## Installation

Manual installation or via HACS (recommended for v1.x).

---

## Known limitations

- Select option labels currently in English
- Price logic depends on sensor format

---

## Support

- GitHub Issues for bugs and feature requests
- Contributions welcome
- Community-driven project

---

**Enjoy smart, safe and transparent battery control.**
