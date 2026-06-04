# mdmaker — "pandoc for e-books"

Multi-format e-book → Markdown converter. Drop a folder, get clean `.md` files.

```bash
pip install -e .
mdmaker books/ -o markdown/ -j 4 --recursive
```

## Supported Formats

| Format | Engine | Requires |
|--------|--------|----------|
| EPUB | Calibre `ebook-convert` | [Calibre](https://calibre-ebook.com) |
| MOBI / PRC | Calibre (MOBI→EPUB→TXT) | Calibre |
| PDF (text) | PyMuPDF (fitz) — fast | — |
| PDF (scanned) | PyMuPDF + Tesseract OCR | [Tesseract](https://github.com/UB-Mannheim/tesseract) |
| DOCX | python-docx | — |
| DOC | Word COM (Windows) / LibreOffice (Linux, planned v0.4) | Word or [LibreOffice](https://www.libreoffice.org) |
| DJVU | DjVuLibre `djvutxt` | [DjVuLibre](https://djvu.sourceforge.net) |
| CHM | 7-Zip extraction + HTML→text | [7-Zip](https://7-zip.org) |
| ZIP | Safe extract → delegate | — |
| XZ | lzma decompress → delegate | — |

## Installation

```bash
git clone <repo-url> mdmaker
cd mdmaker
pip install -e ".[all]"
```

### External Tools (format-dependent)

| Tool | Needed for | Install |
|------|-----------|---------|
| Calibre | EPUB, MOBI, PRC | `winget install calibre` |
| Tesseract OCR | Scanned PDFs | `winget install tesseract-ocr.tesseract` + download `eng.traineddata` |
| DjVuLibre | DJVU | `winget install DjVuLibre.DjView` |
| 7-Zip | CHM | `winget install 7zip.7zip` |
| Word or LibreOffice | DOC | Office/M365 or `winget install TheDocumentFoundation.LibreOffice` |

Check what's installed:

```bash
mdmaker --check
```

## Usage

### CLI

```bash
# Single file
mdmaker book.epub

# Whole directory, 4 parallel workers
mdmaker books/ -o markdown/ -j 4 --recursive

# Preview what would happen
mdmaker books/ --dry-run -r

# Check dependencies
mdmaker --check
```

### GUI

```bash
python -m src.gui
# or via entry point:
mdmaker-gui
```

- First-run setup checks all tools and offers install commands
- Pre-run check warns if tools are missing for the selected files
- Live progress with phase indicator (converting… / OCR running… / extracting…)
- Results are selectable and copyable

## Legal

mdmaker processes **only files you legally own and are able to open**. No DRM removal.
All processing happens locally on your computer. No cloud. No uploads.

## Status

**Stable:** EPUB, PDF (text + OCR), MOBI, DOCX, ZIP, XZ. CLI + GUI on Windows.

**Roadmap:**
- DOC via LibreOffice on Linux/macOS
- Fraktur/old-German OCR via `deu_frak.traineddata`
- Watch mode (`mdmaker watch <folder>`)

## License

See [LICENSE](LICENSE). (To be selected by project owner.)

---

Built with the Eisenagel-Studio decision engine. 11 converters, 1 registry, 0 shortcuts.
