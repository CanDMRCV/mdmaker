"""PDF (text layer) → Markdown via PyMuPDF, with pdfplumber fallback.

Primary: PyMuPDF — ~20x faster, robust with malformed/encrypted PDFs.
Fallback: pdfplumber — for fonts/encodings PyMuPDF yields no text for.

If both fail, we try OCR as a last resort (delegates to pdf_ocr converter).
"""

from pathlib import Path

from ..detector import FormatName
from . import Converter, register, sanitize_filename


def _pdfplumber_extract(path: Path) -> tuple[str, int, int]:
    """Extract text via pdfplumber. Returns (text, num_pages, total_chars)."""
    import pdfplumber

    with pdfplumber.open(str(path)) as pdf:
        pages = pdf.pages
        if not pages:
            return ("", 0, 0)
        text_parts = []
        total_chars = 0
        for i, page in enumerate(pages):
            try:
                text = page.extract_text()
                if text:
                    text_parts.append(f"\n## Page {i + 1}\n\n{text}\n")
                    total_chars += len(text)
            except Exception:
                # Skip pages that fail to extract
                continue
        return ("\n".join(text_parts), len(pages), total_chars)


def _pymupdf_extract(path: Path) -> tuple[str, int, int]:
    """Extract text via PyMuPDF (fitz). Fallback when pdfplumber fails."""
    import pymupdf as fitz

    doc = fitz.open(str(path))
    total_pages = len(doc)
    text_parts = []
    total_chars = 0

    for i in range(total_pages):
        try:
            page = doc[i]
            text = page.get_text("text")
            if text and text.strip():
                text_parts.append(f"\n## Page {i + 1}\n\n{text.strip()}\n")
                total_chars += len(text)
        except Exception:
            continue

    doc.close()
    return ("\n".join(text_parts), total_pages, total_chars)


@register
class _PdfTextConverter:
    label = "PDF text (PyMuPDF / pdfplumber fallback)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt == "pdf_text"

    @staticmethod
    def check_deps() -> list[str]:
        missing = []
        # PyMuPDF (primary)
        try:
            import pymupdf  # noqa: F401
        except ImportError:
            missing.append(
                "PyMuPDF not installed (primary PDF engine).\n"
                "  Fix:  pip install PyMuPDF"
            )
        # pdfplumber (fallback)
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            missing.append(
                "pdfplumber not installed (fallback).\n"
                "  Fix:  pip install pdfplumber"
            )
        return missing

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        text = ""
        total_pages = 0
        total_chars = 0
        method = "PyMuPDF"

        # Primary: PyMuPDF — ~20x faster than pdfplumber at the same text yield
        # (measured: 267-page book 1.5s vs 33s) and fewer merged words.
        try:
            text, total_pages, total_chars = _pymupdf_extract(path)
            if total_chars == 0:
                raise ValueError("PyMuPDF extracted no text")
        except Exception as e1:
            # Fallback 1: pdfplumber (odd fonts/encodings PyMuPDF can't map)
            try:
                text, total_pages, total_chars = _pdfplumber_extract(path)
                method = "pdfplumber (PyMuPDF failed)"
            except Exception as e2:
                # Fallback 2: Try OCR
                try:
                    from .pdf_ocr import _PdfOcrConverter
                    return _PdfOcrConverter.convert(path, output_dir)
                except Exception as e3:
                    raise RuntimeError(
                        f"All PDF extraction methods failed for {path.name}:\n"
                        f"  PyMuPDF: {e1}\n"
                        f"  pdfplumber: {e2}\n"
                        f"  OCR: {e3}"
                    ) from e3

        if total_chars == 0:
            raise ValueError(
                f"No text content extracted from PDF: {path.name}. "
                f"The file may be image-only (try --force to route through OCR)."
            )

        md_path = output_dir / (sanitize_filename(path.stem) + ".md")
        header = (
            f"# {path.stem}\n\n"
            f"> {total_pages} pages · {total_chars:,} chars · "
            f"Converted via {method}\n\n"
        )
        md_path.write_text(header + text, encoding="utf-8")
        return md_path
