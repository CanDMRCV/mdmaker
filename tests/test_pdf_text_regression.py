"""Regression tests for Bug #1: len(doc) after doc.close() — pdf_text.py (C11)."""

import tempfile
from pathlib import Path
import pytest


def _make_text_pdf(pdf_path: Path, num_pages: int = 3) -> int:
    """Create a synthetic text-layer PDF with `num_pages` pages using PyMuPDF.
    Returns the exact page count written (must equal num_pages)."""
    import fitz

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

    def test_fitz_header_shows_correct_page_count(self):
        """_convert_fitz(): the output .md header MUST show the real page count,
        not '?' and not a crash from accessing a closed document."""
        from src.converters.pdf_text import _PdfTextConverter

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pdf_path = tmp / "regression_3page.pdf"
            written = _make_text_pdf(pdf_path, num_pages=3)
            assert written == 3, "synthetic PDF must have 3 pages"

            out_dir = tmp / "out"
            out_dir.mkdir()
            md_path = _PdfTextConverter._convert_fitz(pdf_path, out_dir)

            # (a) output file exists and is non-empty
            assert md_path.exists(), "output .md must exist"
            content = md_path.read_text(encoding="utf-8")
            assert len(content) > 0, "output .md must not be empty"

            # (b) header shows the CORRECT page count (the bug was '?' or crash)
            assert "3 pages" in content.split("\n")[2], (
                f"Header must contain '3 pages', got: {content.split(chr(10))[2]!r}"
            )

            # (c) all three page markers present
            assert "## Page 1" in content
            assert "## Page 2" in content
            assert "## Page 3" in content
            assert "## Page 4" not in content

    def test_pdfplumber_header_shows_correct_page_count(self):
        """_convert_pdfplumber(): defensive — len(pages) captured inside with block."""
        from src.converters.pdf_text import _PdfTextConverter

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            pdf_path = tmp / "regression_plumber_2page.pdf"
            written = _make_text_pdf(pdf_path, num_pages=2)
            assert written == 2

            out_dir = tmp / "out"
            out_dir.mkdir()
            md_path = _PdfTextConverter._convert_pdfplumber(pdf_path, out_dir)

            assert md_path.exists()
            content = md_path.read_text(encoding="utf-8")

            assert "2 pages" in content.split("\n")[2], (
                f"Header must contain '2 pages', got: {content.split(chr(10))[2]!r}"
            )
            assert "## Page 1" in content
            assert "## Page 2" in content

    def test_fitz_many_pages_still_correct(self):
        """Edge case: single-page and 10-page PDFs both report correct count."""
        from src.converters.pdf_text import _PdfTextConverter

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for n in (1, 10):
                pdf_path = tmp / f"regression_{n}page.pdf"
                written = _make_text_pdf(pdf_path, num_pages=n)
                assert written == n

                out_dir = tmp / f"out_{n}"
                out_dir.mkdir()
                md_path = _PdfTextConverter._convert_fitz(pdf_path, out_dir)
                content = md_path.read_text(encoding="utf-8")
                assert f"{n} pages" in content.split("\n")[2], (
                    f"Header for {n}-page PDF must contain '{n} pages'"
                )
