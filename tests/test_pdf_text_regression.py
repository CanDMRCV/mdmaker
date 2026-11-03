"""Regression tests for Bug #1: len(doc) after doc.close() — pdf_text.py (C11).

Ported to the v0.5.x API: the private ``_convert_fitz``/``_convert_pdfplumber``
methods became module-level extractors (``_pymupdf_extract``,
``_pdfplumber_extract``) plus ``_PdfTextConverter.convert``.
"""

import tempfile
from pathlib import Path


def _make_text_pdf(pdf_path: Path, num_pages: int = 3) -> int:
    """Create a synthetic text-layer PDF with `num_pages` pages using PyMuPDF.
    Returns the exact page count written (must equal num_pages)."""
    import pymupdf as fitz

    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text(
            fitz.Point(72, 72),
            f"Page {i + 1} — regression test content line.\nSecond line for page {i + 1}.",
            fontsize=12,
        )
    doc.save(str(pdf_path))
    written_pages = doc.page_count
    doc.close()
    return written_pages


class TestPdfTextRegression:
    """C11 — Prove that the len(doc)-after-close() bug is fixed."""

    def test_fitz_reports_correct_page_count(self):
        """_pymupdf_extract(): real page count, no crash on a closed document."""
        from src.converters.pdf_text import _pymupdf_extract

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "regression_3page.pdf"
            assert _make_text_pdf(pdf_path, num_pages=3) == 3

            text, pages, chars = _pymupdf_extract(pdf_path)
            assert pages == 3, "the bug was '?' or a crash"
            assert chars > 0
            assert "## Page 1" in text
            assert "## Page 2" in text
            assert "## Page 3" in text
            assert "## Page 4" not in text

    def test_convert_header_shows_correct_page_count(self):
        """convert() (pdfplumber path): header shows len(pages) captured inside with block."""
        from src.converters.pdf_text import _PdfTextConverter

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pdf_path = tmp / "regression_plumber_2page.pdf"
            assert _make_text_pdf(pdf_path, num_pages=2) == 2

            out_dir = tmp / "out"
            out_dir.mkdir()
            md_path = _PdfTextConverter.convert(pdf_path, out_dir)

            content = md_path.read_text(encoding="utf-8")
            assert "2 pages" in content.split("\n")[2], (
                f"Header must contain '2 pages', got: {content.split(chr(10))[2]!r}"
            )
            assert "## Page 1" in content
            assert "## Page 2" in content

    def test_fitz_many_pages_still_correct(self):
        """Edge case: single-page and 10-page PDFs both report correct count."""
        from src.converters.pdf_text import _pymupdf_extract

        with tempfile.TemporaryDirectory() as tmp:
            for n in (1, 10):
                pdf_path = Path(tmp) / f"regression_{n}page.pdf"
                assert _make_text_pdf(pdf_path, num_pages=n) == n
                _, pages, _ = _pymupdf_extract(pdf_path)
                assert pages == n, f"{n}-page PDF must report {n} pages"
