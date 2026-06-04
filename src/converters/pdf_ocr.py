"""PDF (scanned/image) → Markdown via PyMuPDF + Tesseract OCR (ADR-001, ADR-005).

Renders pages to 200 DPI images, then OCR with Tesseract. Quality: ~95%
character accuracy (ADR-005). Best-effort: output always produced,
confidence metadata in footer. Degrades on italics, formulas, multi-column.
"""

import shutil
from pathlib import Path

from ..detector import FormatName
from ..security import safe_run
from . import Converter, register


@register
class _PdfOcrConverter:
    label = "PDF scan -> OCR (PyMuPDF + Tesseract)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt == "pdf_scan"

    @staticmethod
    def check_deps() -> list[str]:
        missing = []
        try:
            import fitz  # noqa: F401
        except ImportError:
            missing.append("PyMuPDF not installed.\n  Fix: pip install PyMuPDF")
        try:
            import pytesseract  # noqa: F401
        except ImportError:
            missing.append("pytesseract not installed.\n  Fix: pip install pytesseract")
        if shutil.which("tesseract") is None:
            missing.append(
                "Tesseract OCR not found.\n"
                "  Install: winget install tesseract-ocr.tesseract\n"
                "  Then: download eng.traineddata"
            )
        return missing

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        import fitz  # PyMuPDF
        import pytesseract
        from PIL import Image
        import io

        doc = fitz.open(str(path))
        parts = []
        total_chars = 0
        total_pages = len(doc)

        for i in range(total_pages):
            page = doc[i]
            # Render page to image at 200 DPI
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img, lang="eng")
            if text.strip():
                parts.append(f"\n## Page {i + 1}\n\n{text}\n")
                total_chars += len(text)

        doc.close()

        md_path = output_dir / (path.stem + ".md")
        title = path.stem
        # ADR-005: best-effort with confidence note
        header = (
            f"# {title}\n\n"
            f"> {total_pages} pages · {total_chars:,} chars · "
            f"Converted via Tesseract OCR (200 DPI)\n"
            f"> ⚠️ OCR quality: ~95% typical. Review mathematical formulas and italic text.\n\n"
        )
        md_path.write_text(header + "\n".join(parts), encoding="utf-8")
        return md_path
