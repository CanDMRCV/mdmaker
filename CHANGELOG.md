---
spur: research-werkbank
status: operativ
dept: research
---
> → zurück zum [[_REGISTER|Projekt-Register]]

# Changelog

All notable changes to mdmaker.

## [0.5.2] — 2026-11-03

### Performance
- **PDF: PyMuPDF ist jetzt der Standardweg, pdfplumber nur noch Fallback.** Gemessen an 30 echten Büchern (AUFRUHR): **1258 s → 27 s Wandzeit bei `-j 6` (rund 47×)**, gleiche Textmenge (99–108 % pro Datei), weniger zusammengeklebte Wörter. pdfplumber ist reines Python und blockierte über die GIL auch parallele EPUB-Jobs (EPUB: 3126 s Wartezeit → 24 s).
- **Scan-Erkennung (`classify_pdf`) über PyMuPDF** statt pdfplumber; die 10 Stichprobenseiten sind jetzt über das ganze Buch verteilt statt die ersten 10, damit Cover und Bildtafeln Text-PDFs nicht als Scan einstufen.
- **Vorhandene `.md` wird vor Erkennung und Klassifizierung übersprungen** — Wiederholungsläufe über große Ordner sind sofort fertig.

### Stability
- **Atomare Ausgabe:** Jede Konvertierung schreibt in einen privaten Temp-Ordner und wird per `os.replace` an ihren Platz gelegt. Absturz, Strg+C oder Abbruch hinterlassen keine halbe `.md` mehr, die der nächste Lauf als „fertig" überspringen würde. Zwischendateien (`.txt` von djvu/doc) landen nicht mehr im Ausgabeordner.
- **GUI-Abbruch im Parallelmodus wirkt jetzt** (vorher `if cancel_event.is_set(): pass`): Die Warteschlange wird verworfen, laufende Dateien enden sauber.
- **Strg+C bei `-j >1`** wartet nur noch auf die schon laufenden Dateien, nicht mehr auf die ganze Warteschlange.
- Fehlermeldungen enthalten den Exception-Typ.
- Skip-Prüfung und Konverter nutzen denselben bereinigten Dateinamen (`sanitize_filename`).

### Dependencies
- `PyMuPDF>=1.24.3` ist jetzt Kern-Abhängigkeit (vorher nur im `ocr`-Extra).

### Tests
- Neu: `tests/test_pipeline_stability.py` (atomare Ausgabe, Skip vor Erkennung, Abbruch im Parallelmodus, PyMuPDF als Standard). Der Abbruch-Test hat beim Entwickeln einen Deadlock gefunden: `executor.shutdown(cancel_futures=True)` weckt `as_completed` nicht. Suite: 14/14 grün.

## [0.5.1] — 2026-11-03

### Fixed
- **Race in der Converter-Registry bei `-j >1`:** Das Flag `_registry_loaded` wurde vor den Imports gesetzt, deshalb sahen parallele Worker eine leere Registry (`No converter for 'epub'`/`'mobi'`). Jetzt mit Lock, das Flag wird erst nach den Imports gesetzt. Fund aus dem AUFRUHR-Lauf: 3 von 48 Dateien zu Unrecht fehlgeschlagen.
- **MOBI/AZW/AZW3/PRC gingen an den EPUB-Converter** (`Not a valid ZIP/EPUB file`). Die 0.5.0-Annahme „MOBI ist in der Praxis ZIP" stimmt für echte Kindle-Dateien nicht. Neuer Converter `kindle.py`: Calibre `ebook-convert` → EPUB → der bestehende ebooklib-Pfad. Calibre wird **nur** für diese Formate gebraucht, EPUB bleibt Calibre-frei. Kein Konsolenfenster (`CREATE_NO_WINDOW`).
- **MS Reader `.lit`** wird jetzt erkannt (Magic `ITOLITLS`) und über `kindle.py` konvertiert.
- **Magic-Byte-Erkennung für `BOOKMOBI`/`TEXtREAd` (Offset 60).** Falsch benannte Kindle-Dateien (z. B. `.epub`) werden korrekt geroutet. `MAGIC_READ_SIZE` von 64 auf 72 erhöht.
- **Exit-Code 1**, wenn keine Datei gefunden wurde (fehlende Pfade). Vorher 0, das hat stille Fehlläufe verdeckt.
- **`fitz`-Deprecation-Warnung** bei jedem Lauf: Import umgestellt auf `import pymupdf as fitz`, `PyMuPDF>=1.24.3`.

### Tests
- Neu: `tests/test_kindle_registry.py` (Detector, Routing, Registry-Race im frischen Prozess; schlägt gegen den alten Code in 5 von 5 Läufen an).
- `tests/test_pdf_text_regression.py` auf die v0.5.x-API portiert (`_convert_fitz`/`_convert_pdfplumber` existierten nicht mehr). Suite: 10/10 grün.

## [0.5.0] — 2026-06-16

### Breaking Changes
- **EPUB/MOBI/PRC now pure Python** — ebooklib + BeautifulSoup ersetzen Calibre.
  Calibre ist nicht mehr benötigt. Keine Terminal-Fenster mehr durch externe Prozesse.
- **Magic-byte detection** — erkennt echten Dateityp unabhängig von der Endung.
  Falsch benannte Dateien (z.B. PDF als .epub) werden automatisch korrekt geroutet.

### Fixed
- **Terminal-Fenster beim GUI-Start** — `console=False` im PyInstaller-Spec.
- **6 FAILs bei Batch-Konvertierung** — 5 falsch benannte PDFs + 1 Dummy-Datei korrekt behandelt.
- **Laggy Startup** — Converter-Module werden jetzt lazy geladen (erst bei erster Konvertierung).
- **PDF-Fallback** — pdfplumber → PyMuPDF → OCR (3-stufig, keine PDF scheitert ohne Grund).
- **DOC-Konverter** — LibreOffice headless vor Word COM (kein GUI-Fenster mehr).

### Changed
- Converter synchronisiert mit mdmaker-library v0.5.0
- `tool_detection.py`: ebooklib+bs4 statt Calibre als required
- `main_window.py`: Format→Tool-Mapping aktualisiert
- `pipeline.py`: FileResult/BatchSummary + progress_callback/cancel_event erhalten
- `pyproject.toml`: ebooklib, beautifulsoup4, lxml als core dependencies

## [0.3.4] — 2026-06-06

### Fixed
- **Bug #1:** `len(doc)`-nach-`close()` in `_convert_fitz()` → Header zeigte `?` statt Seitenzahl.
  `total_pages = len(doc)` wird jetzt vor `doc.close()` gespeichert.
- **Issue #2 (defensiv):** `_convert_pdfplumber()` zieht `total_pages = len(pages)` jetzt
  innerhalb des `with`-Blocks — analoger Schutz.
- **Issue #3 (kosmetisch):** `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`
  vor tqdm-Import — beseitigt `�`-Artefakte auf Windows-cp1252-Terminals.

### Added
- **Regressionstests** (`tests/test_pdf_text_regression.py`): 3 parametrisierte Tests
  für `_convert_fitz()` und `_convert_pdfplumber()` — Header-Seitenzahl, Output-Existenz,
  Edge-Case 1/10 Seiten.
- **.exe-Build** (PyInstaller one-file): `mdmaker-gui.exe` als GitHub-Release-Asset,
  unsigniert mit SHA-256-Hash-Verifikation. Externe Tools (Calibre/Tesseract/7-Zip)
  werden NICHT gebündelt — First-Run-Setup-Logik bleibt zuständig.

### Changed
- Version in `pyproject.toml` von 0.1.0 auf 0.3.4 korrigiert (war nie gebumpt worden).
- `src/gui/tool_detection.py`: Docstring als `r"""` raw string deklariert (SyntaxWarning).

## [0.3.3] — 2026-06-04
- Initial public release
- Tesseract-Detektion via Dateisystem+Registry (Rücklauf 5)
- Tool-Detektion gefixt (Rücklauf 4)

## [0.3.2] — 2026-06-03
- First-Run-Setup + Pre-Run-Check (Rücklauf 3 final)

## [0.3.1] — 2026-06-03
- Erste lauffähige GUI + Pipeline

## [0.3.0] — 2026-06-02
- Performance: PyMuPDF (fitz) als primärer PDF-Engine (~10× schneller)
- Actionable Setup
- Scan-in-Worker (nicht-blockierende UI)

## [0.2.2] — 2026-06-02
- Copy-Affordanz
- Präventive OCR-Prüfung

## [0.2.1] — 2026-06-01
- UX-Härtung
- Performance-Instrumentierung

## [0.2.0] — 2026-05-31
- Desktop-GUI (PySide6/Qt)

## [0.1.0] — 2026-05-30
- Alle 11 Converter + Tests + Docs
- Greenfield-Durchstich
