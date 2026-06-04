"""Converter registry (ADR-001). Each converter registers via @register.

Architecture (GoF R3 + Ousterhout R4):
  - Registry: list of Converter objects, populated at import time
  - Each Converter: simple interface (label, can_handle, check_deps, convert)
  - Complex internals (Calibre, Tesseract, Word COM) hidden behind interface
"""

from pathlib import Path
from typing import Protocol, Optional

from ..detector import FormatName


class Converter(Protocol):
    """Interface every converter implements (ADR-001)."""

    label: str  # Human-readable, e.g. "EPUB (Calibre)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool: ...

    @staticmethod
    def check_deps() -> list[str]:
        """Return missing dependency messages (empty = ready)."""
        ...

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        """Convert one file. Return path to the output .md."""
        ...


# ── Registry ──

REGISTRY: list[Converter] = []


def register(converter: Converter) -> Converter:
    """Decorator: register a converter class in the global registry."""
    REGISTRY.append(converter)
    return converter


def find_converter(fmt: FormatName) -> Optional[Converter]:
    """Find the first converter that can handle this format."""
    for conv in REGISTRY:
        if conv.can_handle(fmt):
            return conv
    return None


# ── Import converters so they self-register ──
from . import epub       # noqa: E402, F401
from . import pdf_text   # noqa: E402, F401
from . import pdf_ocr    # noqa: E402, F401
from . import zip_archive  # noqa: E402, F401
from . import xz_archive  # noqa: E402, F401
