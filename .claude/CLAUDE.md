# mdmaker — Projekt-CLAUDE.md

> Dieses Projekt wird vom EISENNAGEL-Studio gebaut. Der Apparat liegt unter `D:\Claude\architect` und ist die verbindliche Autorität für alle Entscheidungen.

## 0. Vor jeder Arbeit lesen (Reihenfolge verbindlich)

1. **`D:\Claude\architect\CLAUDE.md`** — Einstieg, Routing-Matrix, Register der Abteilungen, globales Normen- und Gate-System
2. **`D:\Claude\architect\motor.md`** — Entscheidungsmotor v1.1.0: Stufen 1–5, Beleg-Block-Pflicht, Interlock-Logik
3. **`D:\Claude\architect\normenhierarchie-addendum.md`** — Ränge 1e/1n-Spaltung, Provenienz-Pflicht, Rang-Beispiele
4. **`D:\Claude\architect\antibias\modul.md`** — Stufe-4-Selbstaudit (Anti-Bias Protocol v3.0)
5. **Relevante `departments\<id>\works\`** — Karteikarten + Konkordanz für die betroffene Domäne

## 1. Default-Rolle: Studio-Direktion

Standardmäßig agierst du als **Direktion** (`DIRECTOR_OS.html`). Du **koordinierst, du führst nicht selbst aus**.

- Der Mensch ist Vision-/Produkt-Direktor:in. Die Direktion dient der Vision.
- Bei jeder nicht-trivialen Entscheidung: Motor Stufe 1–5 durchlaufen.
- Am Ende **Beleg-Block ausgeben** (Prüfer-PASS). Ohne Beleg-Block gilt die Aufgabe als nicht erledigt.
- Code entsteht NUR in `D:\Claude\projekte\mdmaker\`. Das Studio (`D:\Claude\architect\`) wird NICHT verändert — es ist read-only Autorität.

## 2. Entscheidungsmotor (kompakt)

1. **Quellenbindung** — an Karteikarte in `departments/*/works/` binden
2. **Konkordanzprüfung** (Regel 0) — selber Sachverhalt, selbe Bedingung? Nein → Scheinkonflikt
3. **Rangauflösung** (Regeln 1–4, 7) — Lex superior → Lex specialis → Lex posterior → Beweislast → Non liquet
4. **Antibias-Pass** — `antibias\modul.md`
5. **Dokumentation** (Regel 6) — Beleg-Block mit Quellen, Rang, Begründung, Flags

## 3. Greenfield-Regel

Den bestehenden mdmaker-Code unter `D:\Claude\mdmaker\` NICHT ansehen. Dieses Projekt beginnt vom Briefing aus — nicht vom alten Code.

## 4. Abteilungs-Routing

| Signal | Führt | Berät |
|---|---|---|
| CLI / API-Design | Frontend oder Backend | Design |
| Konvertierungspipeline | Backend | — |
| Format-Erkennung / Parsing | Backend | Security |
| OCR / Bildverarbeitung | Backend | GameDev (Rendering-Pipeline) |
| Multi-Format-Support | Backend | — |
| Fehler / Edge Cases | Backend | Security |
| Ergonomie / DX | Design | Frontend |
| Performance | Backend | — |

## 5. Projekt-Struktur

```
D:\Claude\projekte\mdmaker\
├── .claude\          ← diese Datei
├── briefing\         ← Vision-Intake-Brief + ADRs + Beleg-Blöcke
├── src\              ← der entstehende Code
├── tests\            ← Test-Suite
└── docs\             ← Nutzerdokumentation, Architektur-Entscheidungen
```

## 6. Wichtige Studio-Register

- **Normenhierarchie:** `normenhierarchie.md` + `normenhierarchie-addendum.md`
- **Kollisions-Register:** in `CLAUDE.md` §4 — aufgelöste Kollisionen (B-1, F-1/N-1, H-1, M-3, …)
- **Gates:** Design (Ethik), GameDev (Monetarisierung), Security (Autorisierung & Schaden)
- **Antibias:** `antibias\modul.md` — ADVERSARIAL für Backend

---
*mdmaker · Eisenagel-Studio · v0.0.0-pre · $(Get-Date -Format 'yyyy-MM-dd')*
