"""Converter registry and shared utilities.

Converters are registered lazily — the first call to :func:`find_converter`
or :func:`check_all_deps` triggers import of all converter modules.
This keeps startup fast and avoids importing heavy dependencies (pdfplumber,
PyMuPDF, pytesseract) until they're actually needed.
"""

import threading
from pathlib import Path
from typing import Protocol, Optional

from ..detector import FormatName


class Converter(Protocol):
    """Interface every converter module implements."""

    label: str  # Human-readable name, e.g. "EPUB (ebooklib)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool: ...

    @staticmethod
    def check_deps() -> list[str]:
        """Return a list of missing dependency messages, or empty if ready."""
        ...

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        """Convert a single file. Return the path to the output .md file."""
        ...


# Registry populated lazily on first access
REGISTRY: list[Converter] = []
_registry_loaded: bool = False
_registry_lock = threading.Lock()


def _ensure_registry() -> None:
    """Import all converter modules so they self-register via @register.

    Only called once — on the first conversion or dependency check.
    This avoids loading pdfplumber, PyMuPDF, pytesseract, etc. at import time.
    """
    global _registry_loaded
    if _registry_loaded:
        return
    # Thread-safe: with -j >1 several workers hit this at once. The flag is set
    # only AFTER all imports, otherwise other threads see an empty REGISTRY
    # ("No converter for 'epub'").
    with _registry_lock:
        if _registry_loaded:
            return
        # Import converter modules — each registers itself via @register
        from . import epub        # noqa: E402, F401
        from . import kindle      # noqa: E402, F401
        from . import pdf_text    # noqa: E402, F401
        from . import pdf_ocr     # noqa: E402, F401
        from . import docx        # noqa: E402, F401
        from . import doc         # noqa: E402, F401
        from . import djvu        # noqa: E402, F401
        from . import chm         # noqa: E402, F401
        from . import xz_archive  # noqa: E402, F401
        from . import zip_archive # noqa: E402, F401
        _registry_loaded = True


def register(converter: Converter) -> Converter:
    REGISTRY.append(converter)
    return converter


def find_converter(fmt: FormatName) -> Optional[Converter]:
    """Find the first registered converter that can handle *fmt*."""
    _ensure_registry()
    for conv in REGISTRY:
        if conv.can_handle(fmt):
            return conv
    return None


def check_all_deps() -> dict[str, list[str]]:
    """Check dependencies for all registered converters.

    Returns
    -------
    dict
        Mapping of converter label -> list of missing dependency messages.
    """
    _ensure_registry()
    issues: dict[str, list[str]] = {}
    for conv in REGISTRY:
        missing = conv.check_deps()
        if missing:
            issues[conv.label] = missing
    return issues


def sanitize_filename(name: str) -> str:
    """Remove characters that are problematic in filenames."""
    for char in '<>:"/\\|?*':
        name = name.replace(char, "_")
    return name[:200]  # Windows MAX_PATH safety
