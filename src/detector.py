"""Format detection and PDF type classification (ADR-001, ADR-005).

PDF-Heuristik (ADR-005): sample first 10 pages. Average < 30 chars/page
→ scanned PDF (OCR pipeline). Otherwise text-based (pdfplumber pipeline).
Calibrated on 106-book corpus; bias: might misclassify image-heavy
text-PDFs as scans. Logged in conversion metadata.
"""

from pathlib import Path
from typing import Literal

FormatName = Literal[
    "epub", "mobi", "prc",
    "pdf_text", "pdf_scan",
    "doc", "docx", "djvu", "chm",
    "xz", "zip",
    "unknown",
]

EXTENSION_MAP: dict[str, FormatName] = {
    ".epub": "epub", ".mobi": "mobi", ".azw": "mobi", ".azw3": "mobi",
    ".prc": "prc", ".pdf": "pdf_text",  # pdf_text is provisional
    ".doc": "doc", ".docx": "docx", ".djvu": "djvu", ".chm": "chm",
    ".xz": "xz", ".zip": "zip",
}

# Magic-byte signatures for archive inner-format detection (ADR-003)
MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF-", ".pdf"),
    (b"PK\x03\x04", ".zip"),       # EPUB/DOCX are ZIP-based
    (b"AT&TFORM", ".djvu"),        # DJVU (older format)
    (b"\x00\x00\x00\x0c\x6a\x50", ".jpeg2000"),
]


def detect_format(path: Path) -> FormatName:
    """Detect initial format by file extension.

    PDFs get provisional ``pdf_text`` — call :func:`classify_pdf` next.
    """
    ext = path.suffix.lower()
    return EXTENSION_MAP.get(ext, "unknown")


def classify_pdf(path: Path, chars_per_page_threshold: float = 30.0) -> FormatName:
    """Sample first 10 pages with pdfplumber to decide text vs. scan.

    Returns ``pdf_text`` if average chars/page >= threshold, else ``pdf_scan``.
    Threshold of 30.0 empirically derived from prior corpus (ADR-005).
    """
    try:
        import pdfplumber
    except ImportError:
        return "pdf_text"  # Can't classify — assume text

    try:
        with pdfplumber.open(str(path)) as pdf:
            total_chars = 0
            pages = pdf.pages
            if not pages:
                return "pdf_text"
            sample_pages = min(10, len(pages))
            for page in pages[:sample_pages]:
                text = page.extract_text()
                if text:
                    total_chars += len(text)
            avg = total_chars / sample_pages if sample_pages > 0 else 0
            return "pdf_scan" if avg < chars_per_page_threshold else "pdf_text"
    except Exception:
        return "pdf_text"


def detect_inner_format(raw_path: Path) -> str:
    """Peek at magic bytes to guess the extension of a decompressed file (ADR-003)."""
    try:
        with open(str(raw_path), "rb") as f:
            magic = f.read(32)
        for sig, ext in MAGIC_SIGNATURES:
            if magic.startswith(sig):
                return ext
    except OSError:
        pass
    return ""
