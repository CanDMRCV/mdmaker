"""PDF (scanned/image) → Markdown via PyMuPDF + Tesseract OCR (ADR-001, ADR-005).

Renders pages to 200 DPI images, then OCR with Tesseract. Quality: ~95%
character accuracy (ADR-005). Best-effort: output always produced,
confidence metadata in footer.

Rücklauf 5: Robust tesseract resolution (same as tool_detection.py).
  Checks filesystem + registry, not PATH — avoids PATH inheritance bug.
"""

import shutil
import os
import winreg
from pathlib import Path

from ..detector import FormatName
from ..security import safe_run
from . import Converter, register


def _resolve_tesseract() -> str:
    """Find tesseract.exe via filesystem + registry. Returns absolute path or ''."""
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR" / "tesseract.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Tesseract-OCR" / "tesseract.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        for subkey in [r"SOFTWARE\Tesseract-OCR", r"SOFTWARE\WOW6432Node\Tesseract-OCR"]:
            try:
                key = winreg.OpenKey(root, subkey)
                val, _ = winreg.QueryValueEx(key, "InstallDir")
                winreg.CloseKey(key)
                exe = Path(val) / "tesseract.exe"
                if exe.exists():
                    return str(exe)
            except OSError:
                pass
    found = shutil.which("tesseract")
    return found or ""


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
        # Robust tesseract resolution
        exe = _resolve_tesseract()
        if not exe:
            missing.append(
                "Tesseract OCR not found.\n"
                "  Install: winget install tesseract-ocr.tesseract\n"
                "  Then RESTART mdmaker (PATH update needed)."
            )
        return missing

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        import fitz
        import pytesseract
        from PIL import Image
        import io

        # Robust resolution: find tesseract + tessdata (Rücklauf 5+6)
        tesseract_exe = _resolve_tesseract()
        if tesseract_exe:
            pytesseract.pytesseract.tesseract_cmd = tesseract_exe
            # Find tessdata: check install dir, then LOCALAPPDATA (user-writable)
            for prefix in [
                Path(tesseract_exe).parent,  # C:\Program Files\Tesseract-OCR
                Path(os.environ.get("LOCALAPPDATA", "")),  # user-writable
            ]:
                if (prefix / "tessdata" / "eng.traineddata").exists():
                    os.environ["TESSDATA_PREFIX"] = str(prefix)
                    break

        doc = fitz.open(str(path))
        parts = []
        total_chars = 0
        total_pages = len(doc)

        for i in range(total_pages):
            page = doc[i]
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img, lang="eng")
            if text.strip():
                parts.append(f"\n## Page {i + 1}\n\n{text}\n")
                total_chars += len(text)

        doc.close()

        md_path = output_dir / (path.stem + ".md")
        title = path.stem
        header = (
            f"# {title}\n\n"
            f"> {total_pages} pages · {total_chars:,} chars · "
            f"Converted via Tesseract OCR (200 DPI)\n"
            f"> ⚠️ OCR quality: ~95% typical. Review mathematical formulas and italic text.\n\n"
        )
        md_path.write_text(header + "\n".join(parts), encoding="utf-8")
        return md_path
