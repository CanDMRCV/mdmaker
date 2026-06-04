# Brief — Frontend (beratend, CLI-Ergonomie)

> Inbound D-03. Berät Backend bei CLI-Design. Führt NICHT selbst aus.

## 1. Auftrag

Definiere das CLI-Interface: Kommando-Struktur, Ausgabe, Fortschritt, Fehlermeldungen. Backend implementiert nach diesen Vorgaben.

## 2. CLI-Spezifikation

```
mdmaker <eingabe>... -o <ausgabe>/ [-j <n>] [--recursive] [--dry-run] [--force] [--check]

Argumente:
  eingabe             Pfade zu Dateien/Ordnern (mehrere erlaubt)

Optionen:
  -o, --output DIR    Ausgabeverzeichnis (default: _md_output)
  -j, --jobs N        Parallele Worker (default: 1 = sequentiell)
  -r, --recursive     Ordner rekursiv durchsuchen
  -f, --force         Neu konvertieren auch wenn .md existiert
  --dry-run           Vorschau ohne Konvertierung
  --check             Abhängigkeiten prüfen und beenden
  -V, --version       Version anzeigen

Ausgabe-Struktur:
  <output>/
    Buch1.md
    Buch2.md
    ...
```

## 3. Fortschrittsanzeige

- **Sequentiell:** Fortschrittsbalken mit aktuellem Dateinamen: `Converting: 45/283 (15%) — Designing Data-Intensive Applications.epub`
- **Parallel:** Gleicher Balken, pro fertigem Job ein Tick.
- **Nach Abschluss:** Zusammenfassung: `[OK] 278  [SKIP] 3  [FAIL] 2  —  142.3s`
- **OCR-Warnung:** `[OCR] Buch.pdf: ~87% confidence — review recommended`

## 4. Fehlerkultur (Norman R2: Feedback)

- Fehler NIE still. Jeder FAIL wird mit Format, Converter und Grund gemeldet.
- `--dry-run` zeigt JEDE geplante Aktion mit Converter-Label.
- `--check` listet Farbe/FORMATIERT, was fehlt, mit Installationshinweis.
- Unbekanntes Format → klare Meldung, nicht einfach überspringen.

## 5. Quellenbindung

- **Norman Design of Everyday Things (R2):** Feedback, Visibility of System Status. Der Nutzer muss jederzeit wissen, was das Tool tut und ob etwas schiefging. [Karte: `design-of-everyday-things`]
- **CLI-Verb-Erst-Argument:** `mdmaker <eingabe> -o <ausgabe>` — das WICHTIGSTE zuerst.

## 6. Übergabe an Backend

Das CLI-Modul (`src/cli.py`) ruft die Backend-Pipeline auf. Frontend spezifiziert das WAS, Backend implementiert das WIE des Interfaces.

---
*Brief Frontend v1.0 · erstellt von Direktion · 4. Juni 2026*
