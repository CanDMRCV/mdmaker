"""Format detection via magic bytes + PDF type classification.

Uses magic-byte signatures first, falling back to file extension.
This handles mislabeled files (e.g., PDF saved as .epub) and detects
corrupted/dummy files early.

Magic-byte references:
    https://en.wikipedia.org/wiki/List_of_file_signatures
"""

from pathlib import Path
from typing import Literal

FormatName = Literal[
    "epub", "mobi", "prc", "pdf_text", "pdf_scan",
    "doc", "docx", "djvu", "chm", "xz", "zip", "lit", "unknown",
]

# Magic-byte signatures for common formats.
# (signature_bytes, offset, label_for_detection)
MAGIC_SIGNATURES: list[tuple[bytes, int, str]] = [
    (b"%PDF-", 0, "pdf"),
    (b"PK\x03\x04", 0, "zip_based"),   # EPUB, DOCX, XZ, ZIP all use ZIP
    (b"Rar!\x1a\x07", 0, "unknown"),    # RAR — not supported
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", 0, "ole"),  # Old .doc (OLE2)
    (b"AT&TFORM", 0, "djvu"),
    (b"FORM", 0, "djvu"),               # DJVU alternative
    (b"\x1f\x8b\x08", 0, "gzip"),       # GZIP (maybe tar.gz)
    (b"\xfd7zXZ\x00", 0, "xz"),         # XZ
    (b"<!DOCTYPE html", 0, "html"),     # Mislabeled HTML
    (b"<html", 0, "html"),              # HTML
    (b"<?xml", 0, "xml"),               # XML
    (b"<!doctype html", 0, "html"),     # HTML (case insensitive check below)
    (b"ITOLITLS", 0, "lit"),             # MS Reader .lit
    (b"BOOKMOBI", 60, "mobi"),           # Mobipocket / KF8 (.mobi .azw .azw3) — PalmDB type at offset 60
    (b"TEXtREAd", 60, "prc"),            # PalmDOC (.prc / old .mobi)
]

# Minimum file size to be considered valid (in bytes)
MIN_VALID_SIZE = 100

# Maximum size to read for magic-byte detection
MAGIC_READ_SIZE = 72  # BOOKMOBI sits at offset 60..68


def _read_magic(path: Path) -> bytes:
    """Read the first MAGIC_READ_SIZE bytes of a file for type detection."""
    try:
        with open(str(path), "rb") as f:
            return f.read(MAGIC_READ_SIZE)
    except Exception:
        return b""


def detect_by_magic(path: Path) -> str:
    """Detect format by magic bytes. Returns 'unknown' if no match.

    Handles compound cases:
    - ZIP-based: EPUB, DOCX, XZ, ZIP all start with PK. We return
      'zip_based' and let the extension disambiguate.
    - OLE2: Old .doc format, but also some other MS formats.
    """
    magic = _read_magic(path)

    if len(magic) == 0:
        return "unknown"

    for sig, offset, label in MAGIC_SIGNATURES:
        if len(magic) >= offset + len(sig):
            if magic[offset:offset + len(sig)] == sig:
                if label == "zip_based":
                    # Check if it's actually XZ (FD 37 7A 58 5A 00)
                    # XZ files also start with bytes that can match PK in
                    # some edge cases, but standard XZ has its own signature
                    return "zip_based"
                if label == "html":
                    return "html"
                return label

    # Case-insensitive HTML check
    magic_lower = magic[:32].lower()
    if b"<!doctype html" in magic_lower or b"<html" in magic_lower:
        return "html"
    if b"<?xml" in magic_lower:
        return "xml"

    return "unknown"


def detect_format(path: Path) -> FormatName:
    """Detect the format of a book file.

    Uses magic bytes first, then falls back to extension.
    Handles mislabeled files (e.g., PDF with .epub extension).

    Returns 'unknown' if the file cannot be identified or is too small.
    """
    # Quick size check
    try:
        size = path.stat().st_size
    except Exception:
        return "unknown"

    if size < MIN_VALID_SIZE:
        return "unknown"

    # Step 1: Magic bytes
    magic_type = detect_by_magic(path)

    # Step 2: Resolve magic type to FormatName
    if magic_type == "pdf":
        return "pdf_text"  # Will be classified further by classify_pdf
    elif magic_type == "djvu":
        return "djvu"
    elif magic_type == "html" or magic_type == "xml":
        # Mislabeled HTML/XML — not a supported book format
        return "unknown"
    elif magic_type in ("mobi", "prc", "lit"):
        return magic_type  # binary, regardless of (often wrong) extension
    elif magic_type == "ole":
        return "doc"
    elif magic_type == "xz":
        return "xz"
    elif magic_type == "zip_based":
        # Disambiguate ZIP-based formats by extension
        ext = path.suffix.lower()
        if ext in (".epub", ".mobi", ".prc", ".azw", ".azw3"):
            return "epub"  # ZIP container with Kindle extension = mislabeled EPUB
        elif ext == ".docx":
            return "docx"
        elif ext == ".zip":
            return "zip"
        elif ext == ".xz":
            return "xz"
        else:
            # Unknown ZIP — try extension-based map
            pass
    elif magic_type == "gzip":
        return "unknown"  # tar.gz not supported

    # Step 3: Fallback to extension
    ext = path.suffix.lower()
    ext_map: dict[str, FormatName] = {
        ".epub": "epub",
        ".mobi": "mobi",
        ".azw": "mobi",
        ".azw3": "mobi",
        ".prc": "prc",
        ".pdf": "pdf_text",
        ".doc": "doc",
        ".docx": "docx",
        ".djvu": "djvu",
        ".chm": "chm",
        ".xz": "xz",
        ".zip": "zip",
        ".lit": "lit",
    }
    return ext_map.get(ext, "unknown")


def classify_pdf(path: Path, chars_per_page_threshold: float = 30.0) -> FormatName:
    """Open a PDF with pdfplumber to decide whether it's text-based or scanned.

    Returns ``"pdf_text"`` if the average chars/page >= *chars_per_page_threshold*,
    otherwise ``"pdf_scan"`` (needs OCR).

    Parameters
    ----------
    path:
        Path to the PDF file.
    chars_per_page_threshold:
        Minimum average characters per page to classify as text-based.
        Default 30.0 — empirically derived from a 106-book corpus.
    """
    try:
        import pymupdf
    except ImportError:
        # Can't classify — assume text, let pdf_text converter try
        return "pdf_text"

    try:
        with pymupdf.open(str(path)) as doc:
            n = doc.page_count
            if n == 0:
                return "pdf_text"
            # 10 pages spread over the whole book — the first pages are often
            # image-only covers/plates and would misclassify text PDFs as scans.
            sample = sorted({i * n // 10 for i in range(10)})
            total_chars = sum(len(doc[i].get_text("text").strip()) for i in sample)
            if total_chars / len(sample) < chars_per_page_threshold:
                return "pdf_scan"
            return "pdf_text"
    except Exception:
        return "pdf_text"  # Conservative fallback
