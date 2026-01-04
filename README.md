# Zendure SmartFlow AI

**Intelligente, preis-, PV- und lastbasierte Steuerung für Zendure SolarFlow Systeme in Home Assistant**

---

## 🇩🇪 Deutsch

## Überblick

**Zendure SmartFlow AI** ist eine Home-Assistant-Integration zur **stabilen, wirtschaftlichen und sicheren** Steuerung von Zendure-SolarFlow-Systemen.

Ab **Version 1.2.0** kombiniert die Integration:

- ☀️ **PV-Erzeugung**
- 🏠 **Hausverbrauch**
- 🔋 **Batterie-SoC**
- 💶 **Strompreise (optional, inkl. Vorplanung)**

zu **kontextbasierten Lade- und Entladeentscheidungen**.

👉 Ziel ist **nicht maximale Aktivität**, sondern **optimales Verhalten**:
- Laden, wenn es sinnvoll ist  
- Entladen, wenn es wirtschaftlich ist  
- Stillstand, wenn nichts gewonnen wird  

---

## Warum diese Integration?

Viele bestehende Lösungen arbeiten mit:
- festen Zeitplänen
- starren Preisgrenzen
- simplen Wenn-Dann-Regeln

**Zendure SmartFlow AI** verfolgt bewusst einen anderen Ansatz:

> **Kontext statt Regeln.**

Jede Entscheidung basiert immer auf der **aktuellen Gesamtsituation**:
- Wie hoch ist die PV-Leistung?
- Wie hoch ist die Hauslast?
- Wie voll ist der Akku?
- Wie teuer ist Strom **jetzt** – und **später**?

---

## Grundprinzip (die „KI“)

Die Integration bewertet zyklisch:

- PV-Leistung  
- Hausverbrauch  
- Netzbezug / Einspeisung  
- Batterie-SoC  
- aktueller Strompreis (optional)  

Daraus ergeben sich drei Aktionen:
- 🔌 **Laden**
- 🔋 **Entladen**
- ⏸️ **Nichts tun**

Die Logik ist **bewusst konservativ**:
- Kein unnötiges Entladen  
- Kein sinnloses Laden  
- Sicherheit hat immer Vorrang  

---

## 🧠 Neu ab Version 1.2.0: Preis-Vorplanung

### Was bedeutet Preis-Vorplanung?

Die KI betrachtet **nicht nur den aktuellen Strompreis**, sondern analysiert **kommende Preisspitzen** im Tagesverlauf.

Ziel:

> **Vor einer bekannten Preisspitze möglichst günstig laden –  
aber nur, wenn es sinnvoll ist.**

---

### Wie funktioniert das?

1. Die KI sucht die **nächste relevante Preisspitze**
   - sehr teuer **oder**
   - teuer + konfigurierbare Gewinnmarge

2. Der Zeitraum **vor dieser Spitze** wird analysiert

3. Daraus wird ein **„Billigfenster“** (günstigste ~25 %) ermittelt

4. **Nur wenn:**
   - aktuell ein günstiger Slot aktiv ist  
   - kein PV-Überschuss vorhanden ist  
   - der Akku nicht voll ist  

👉 wird **gezielt aus dem Netz geladen**

---

### Wichtig zu wissen (absichtlich so!)

- Preis-Vorplanung ist **situativ**
- Sie ist **nicht dauerhaft aktiv**
- Sensoren können korrekt auf **`unknown`** stehen

**Beispiele:**
- Kein Peak in Sicht → keine Planung  
- Akku bereits voll → keine Planung  
- PV-Überschuss vorhanden → Planung pausiert  

➡️ **`unknown` oder `false` bedeutet nicht „Fehler“, sondern „keine Aktion nötig“.**

---

## Anti-Schwingung & Regelstabilität (ab 1.2.0)

Ein häufiges Problem bei Batterie-Regelungen sind **Leistungs-Oszillationen**, z. B.:

1200 W Defizit → 1100 W Entladung
100 W Defizit  → 100 W Entladung
1100 W Defizit → …

**Zendure SmartFlow AI verhindert das aktiv durch:**

- Mindest-Haltezeiten für Entladeleistungen  
- Leistungs-Rampen (keine Sprünge)  
- Hysterese gegen Messrauschen  
- Sauberes Start-/Stop-Verhalten  

➡️ Ergebnis: **ruhige, stabile Regelung ohne Flattern**

---

## Betriebsmodi

### 🔹 Automatik (empfohlen)

- PV-Überschuss wird genutzt
- Teurer Strom wird vermieden
- Preis-Vorplanung aktiv
- Optimal für ~95 % aller Nutzer

---

### 🔹 Sommer

- Fokus auf Eigenverbrauch
- Entladung **nur bei sehr teurem Strom**
- Keine aggressive Preis-Strategie

---

### 🔹 Winter

- Preisorientierte Nutzung des Akkus
- Entladung bereits bei „teurem“ Strom
- Preis-Vorplanung aktiv

---

### 🔹 Manuell

- KI greift nicht ein
- Laden / Entladen / Standby manuell
- Ideal für Tests oder Sonderfälle

---

## Sicherheitsmechanismen

### SoC Minimum
- Unterhalb dieses Wertes wird **nicht entladen**

### SoC Maximum
- Oberhalb dieses Wertes wird **nicht weiter geladen**

---

## 🧯 Notladefunktion (verriegelt)

- Aktivierung bei kritischem SoC
- Laden bis zum SoC Minimum
- Automatisches Beenden
- Kein Dauer-Notmodus

---

## Entitäten in Home Assistant

### Select
- Betriebsmodus
- Manuelle Aktion

### Number
- SoC Minimum / Maximum
- Max. Lade- & Entladeleistung
- Notladeleistung
- Notladung ab SoC
- Sehr-Teuer-Schwelle
- Gewinnmarge

### Sensoren
- Systemstatus
- KI-Status
- KI-Empfehlung
- Entscheidungsgrund
- Hauslast
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
- Batterie-SoC Sensor
- PV-Leistungssensor
- Optional: Strompreis-Sensor (z. B. Tibber)

---

## Installation

### Manuell
1. Repository herunterladen  
2. Ordner `zendure_smartflow_ai` nach  
   `/config/custom_components/` kopieren  
3. Home Assistant neu starten  
4. Integration hinzufügen  

### HACS
> Ab Version 1.x vorgesehen

---

## Support & Mitwirkung

- GitHub Issues für Bugs & Feature-Wünsche
- Pull Requests willkommen
- Community-Projekt

---

**Zendure SmartFlow AI – ruhig, erklärbar, wirtschaftlich.**
