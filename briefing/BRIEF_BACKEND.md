# Brief — Backend (führt)

> Inbound D-03. Führende Abteilung: **Backend**. Beratend: Security, Frontend.

## 1. Auftrag

Baue den **mdmaker CLI-Kern**: Format-Detektion, Converter-Registry, Pipeline-Orchestrator, und alle 11 Format-Converter. Jeder Converter ist ein eigenes, in einer Registry selbst-registrierendes Modul. Neues Format = neues Modul (~50 Zeilen).

## 2. Architektur-Entscheidungen (vorab getroffen)

| Entscheidung | Wert | ADR |
|---|---|---|
| Pipeline-Muster | Registry + Strategy (jeder Converter eine Strategie) | ADR-001 |
| DOC-Schnittstelle | Tiefes Modul: `DocConverter` interface, Word-COM Implementierung, LibreOffice-Stub | ADR-002 |
| Archiv-Verhalten | Nur Single-Book: 1 PDF/EPUB im Archiv → extrahieren & delegieren. Multi-File → Fehler. | ADR-003 |
| CHM auf Linux/macOS | `7z` cross-platform → HTML→Text mit eigenem Parser (kein hh.exe auf Linux) | ADR-004 |
| OCR-Qualität | Best-effort: Ausgabe immer, Footer-Metadaten mit Confidence-Warnung | ADR-005 |
| Parallelität | `ThreadPoolExecutor` für I/O-gebundene, erkennbar via `-j <n>` | ADR-006 |
| Namensschema | `Titel - Autor, Jahr.md` via Metadaten, Fallback: Dateiname | ADR-007 |

## 3. Quellenbindung

- **Ousterhout (R4):** A Philosophy of Software Design → tiefe Module, strategisches Design. DOC als tiefes Modul hinter DocConverter. [Karte: `departments/backend/works/philosophy-of-software-design.md`]
- **DDIA (R2):** Pipeline-Design: Reliability, Maintainability als Architektur-Charakteristiken. [Karte: `departments/backend/works/designing-data-intensive-applications.md`]
- **Release It! (R3):** Stability Patterns: Timeout, Circuit Breaker für externe Tools (Calibre, Tesseract, Word COM). [Karte: `departments/backend/works/release-it.md`]
- **Khorikov Unit Testing (R3):** Testbare Converter: jedes Modul testet isoliert. [Karte: `departments/backend/works/unit-testing.md`]
- **GoF Design Patterns (R3):** Registry/Strategy für Converter. [Karte: `departments/backend/works/design-patterns-gof.md`]

## 4. Durchstich (Definition of Done)

1. `mdmaker <ordner> -o <out>` konvertiert EPUB + PDF(Text) + ein Archiv (ZIP oder XZ) end-to-end zu .md.
2. Converter-Registry routet Format → Converter.
3. PDF-Heuristik: sample ~10 Seiten, <30 chars/page → OCR-Pipeline.
4. `--check` listet fehlende externe Tools.
5. `--dry-run` zeigt, was passieren würde.

## 5. Schnittstellen zu anderen Abteilungen

- **Security:** Converter befolgen Härtungs-Vorgaben aus SECURITY-Brief.
- **Frontend:** CLI-Interface folgt UX-Vorgaben aus FRONTEND-Brief.
- **Naht Backend↔Security:** Bei Konflikt zwischen "einfach" und "sicher" eskaliert die Direktion.

---
*Brief Backend v1.0 · erstellt von Direktion · 4. Juni 2026*
