# Zendure SmartFlow AI

**Intelligente, preis-, PV- und lastbasierte Steuerung für Zendure SolarFlow Systeme in Home Assistant**

---

## 🇩🇪 Deutsch

## Überblick

**Zendure SmartFlow AI** ist eine Home-Assistant-Integration zur **stabilen, wirtschaftlichen und transparenten** Steuerung von Zendure-SolarFlow-Systemen.

Ab **Version 1.2.x** kombiniert die Integration:

- ☀️ **PV-Erzeugung**
- 🏠 **Hauslast (Gesamtverbrauch)**
- 🔋 **Batterie-SoC**
- 💶 **Dynamische Strompreise (optional, inkl. Vorplanung)**

zu **kontextbasierten Lade- und Entladeentscheidungen**.

👉 Ziel ist **nicht maximale Aktivität**, sondern **maximaler Nutzen**:
- Laden, wenn es wirtschaftlich sinnvoll ist  
- Entladen, wenn Netzbezug vermieden werden kann  
- Stillstand, wenn keine Verbesserung möglich ist  

---

## Warum diese Integration?

Viele bestehende Lösungen arbeiten mit:
- festen Zeitplänen
- starren Preisgrenzen
- simplen Wenn-Dann-Regeln

**Zendure SmartFlow AI** verfolgt bewusst einen anderen Ansatz:

> **Kontext statt Regeln.**

Jede Entscheidung basiert auf der **aktuellen Gesamtsituation**:
- Wie hoch ist die aktuelle Hauslast?
- Gibt es Netzbezug oder Einspeisung?
- Wie voll ist der Akku?
- Wie teuer ist Strom **jetzt** – und **in naher Zukunft**?

---

## Grundprinzip (die „KI“)

Die Integration bewertet zyklisch:

- PV-Leistung  
- Hauslast (Netzbezug + Eigenverbrauch)  
- Netzdefizit / Einspeiseüberschuss  
- Batterie-SoC  
- aktuellen Strompreis (optional)  

Daraus ergeben sich drei mögliche Aktionen:
- 🔌 **Laden**
- 🔋 **Entladen**
- ⏸️ **Nichts tun**

Die Logik ist **bewusst nachvollziehbar**:
- Keine unnötigen Aktionen  
- Keine verdeckten Automatismen  
- Sicherheit & Wirtschaftlichkeit haben Vorrang  

---

## 🧠 Preis-Vorplanung (ab Version 1.2.0)

### Was bedeutet Preis-Vorplanung?

Die KI betrachtet **nicht nur den aktuellen Strompreis**, sondern analysiert **kommende Preisspitzen** im Tagesverlauf.

Ziel:

> **Vor einer bekannten Preisspitze günstig Energie speichern –  
aber nur, wenn es wirklich sinnvoll ist.**

---

### Wie funktioniert das?

1. Analyse der kommenden Preisentwicklung  
2. Erkennung einer relevanten Preisspitze:
   - **sehr teuer** oder  
   - **teuer + konfigurierbare Gewinnmarge**
3. Bewertung des Zeitraums **vor dieser Spitze**
4. Laden aus dem Netz **nur wenn**:
   - aktuell ein günstiger Zeitraum aktiv ist  
   - kein relevanter PV-Überschuss vorhanden ist  
   - der Akku nicht voll ist  

➡️ **Kein Dauerladen, kein Zwang, keine Zeitpläne**

---

### Wichtig zu wissen

- Preis-Vorplanung ist **situativ**
- Sie ist **nicht permanent aktiv**
- Sensoren können korrekt auf **`unknown`** stehen

**Beispiele:**
- Kein Peak in Sicht → keine Planung  
- Akku voll → keine Planung  
- PV-Überschuss → Planung pausiert  

➡️ **`unknown` bedeutet „keine Aktion nötig“, nicht „Fehler“.**

---

## ⚡ Extrem teure Strompreise (ab Version 1.2.1)

Ab **v1.2.1** haben **extreme Preisspitzen absolute Priorität**.

### Sehr-Teuer-Schwelle
Wird der aktuelle Strompreis **≥ Sehr-Teuer-Schwelle**, dann gilt:

- Entladung hat **immer Vorrang**
- unabhängig vom Modus (Sommer / Winter / Automatik)
- unabhängig von PV-Überschuss

### Temporär unbegrenzte Entladung
In dieser Situation:
- wird das konfigurierte Entlade-Limit **temporär ignoriert**
- es wird **genau so viel Leistung abgegeben wie benötigt**
- begrenzt nur durch die Hardware (max. 2400 W)

➡️ Ziel: **Netzbezug bei extremen Preisen maximal vermeiden**

---

## Betriebsmodi

### 🔹 Automatik (empfohlen)

- PV-Überschuss wird genutzt
- Teurer Strom wird vermieden
- Preis-Vorplanung aktiv
- Sehr-teure Preise haben immer Vorrang

---

### 🔹 Sommer

- Fokus auf maximale Autarkie
- Akku deckt Hauslast
- Sehr-teure Preisspitzen haben Vorrang vor PV-Logik

---

### 🔹 Winter

- Fokus auf Kostenersparnis
- Entladung bereits bei „teurem“ Strom
- Preis-Vorplanung aktiv

---

### 🔹 Manuell

- Keine KI-Eingriffe
- Laden / Entladen / Standby manuell
- Ideal für Tests & Sonderfälle

---

## Sicherheitsmechanismen

### SoC Minimum
- Unterhalb dieses Wertes wird **nicht entladen**

### SoC Maximum
- Oberhalb dieses Wertes wird **nicht weiter geladen**

---

## 🧯 Notladefunktion (verriegelt)

- Aktivierung bei kritischem SoC
- Laden bis mindestens SoC-Minimum
- Automatisches Beenden
- Kein Dauer-Notmodus

---

## Entitäten in Home Assistant

### Select
- Betriebsmodus
- Manuelle Aktion

### Number
- SoC Minimum / Maximum
- Max. Ladeleistung
- Max. Entladeleistung (Normalbetrieb)
- Notladeleistung
- Notladung ab SoC
- Sehr-Teuer-Schwelle
- Gewinnmarge (%)

### Sensoren
- Systemstatus
- KI-Status
- KI-Empfehlung
- Entscheidungsgrund
- **Hauslast (Gesamtverbrauch)**
- Aktueller Strompreis
- Ø Ladepreis Akku
- Gewinn / Ersparnis
- Preis-Vorplanung aktiv
- Ziel-SoC Preis-Vorplanung
- Planungsbegründung

---

## Voraussetzungen

- Home Assistant (aktuelle Version)
- Zendure SolarFlow
- Batterie-SoC-Sensor
- PV-Leistungssensor
- Optional: dynamischer Strompreis-Sensor (z. B. Tibber)

---

## Installation

### Über HACS
1. HACS muß in Home Assistant installiert sein 
2. HACS aufrufen und rechts oben auf die 3 Punkte klicken,   
3. Den Menüpunkt `Benutzerdefinierte Repositories` anklicken 
4. Im Feld Repository `https://github.com/PalmManiac/zendure-smartflow-ai` einfügen,
   darunter als `Typ` Integration auswählen und auf `Hinzufügen` klicken.
5. Nun taucht sie in der HACS-Liste auf und kann installiert werden.

---

## Support & Mitwirkung

- GitHub Issues für Bugs & Feature-Wünsche
- Pull Requests willkommen
- Community-Projekt

---

**Zendure SmartFlow AI – erklärbar, stabil, wirtschaftlich.**
