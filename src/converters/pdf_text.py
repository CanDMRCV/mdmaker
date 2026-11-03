"""PDF (text layer) → Markdown via pdfplumber, with PyMuPDF fallback.

Primary: pdfplumber — handles tables, columns, and text flow well.
Fallback: PyMuPDF (fitz) — more robust at opening malformed PDFs,
    handles encrypted PDFs better, and catches files pdfplumber rejects.

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
    label = "PDF text (pdfplumber / PyMuPDF fallback)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt == "pdf_text"

    @staticmethod
    def check_deps() -> list[str]:
        missing = []
        # pdfplumber (primary)
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            missing.append(
                "pdfplumber not installed.\n"
                "  Fix:  pip install pdfplumber"
            )
        # PyMuPDF (fallback) — optional but strongly recommended
        try:
            import pymupdf as fitz  # noqa: F401
        except ImportError:
            missing.append(
                "PyMuPDF not installed (optional fallback).\n"
                "  Fix:  pip install PyMuPDF"
            )
        return missing

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        text = ""
        total_pages = 0
        total_chars = 0
        method = "pdfplumber"

        # Primary: pdfplumber
        try:
            text, total_pages, total_chars = _pdfplumber_extract(path)
        except Exception as e1:
            # Fallback 1: PyMuPDF
            try:
                import pymupdf as fitz  # noqa: F811
                text, total_pages, total_chars = _pymupdf_extract(path)
                method = "PyMuPDF (pdfplumber failed)"
            except Exception as e2:
                # Fallback 2: Try OCR
                try:
                    from .pdf_ocr import _PdfOcrConverter
                    return _PdfOcrConverter.convert(path, output_dir)
                except Exception as e3:
                    raise RuntimeError(
                        f"All PDF extraction methods failed for {path.name}:\n"
                        f"  pdfplumber: {e1}\n"
                        f"  PyMuPDF: {e2}\n"
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
