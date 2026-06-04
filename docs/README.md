# mdmaker — "pandoc for e-books"

Multi-format e-book → Markdown converter. Built by the Eisenagel-Studio.

```bash
pip install -e .
mdmaker books/ -o markdown/ -j 4 --recursive
```

## Supported Formats

| Format | Converter | Requires |
|--------|-----------|----------|
| EPUB | Calibre ebook-convert | [Calibre](https://calibre-ebook.com) |
| MOBI/PRC | Calibre (MOBI→EPUB→TXT) | Calibre |
| PDF (text) | pdfplumber | — |
| PDF (scan) | PyMuPDF + Tesseract OCR | Tesseract |
| DOCX | python-docx | — |
| DOC | Word COM (Win) / LibreOffice (Linux, v0.2) | Word or LibreOffice |
| DJVU | DjVuLibre djvutxt | [DjVuLibre](https://djvu.sourceforge.net) |
| CHM | 7-Zip | [7-Zip](https://7-zip.org) |
| ZIP | Safe extract → delegate | — |
| XZ | lzma decompress → delegate | — |

## Security

All input is treated as untrusted. mdmaker protects against:
- **Zip bombs** (decompression ratio limit: 100:1)
- **Path traversal** (..  entries rejected)
- **XXE attacks** (defusedxml for DOCX/EPUB XML)
- **Shell injection** (all subprocess.run use shell=False)
- **Resource exhaustion** (timeouts, size limits)

## License

MIT — see LICENSE.
