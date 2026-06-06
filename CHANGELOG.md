# Changelog

All notable changes to mdmaker.

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
