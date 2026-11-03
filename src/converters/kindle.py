"""MOBI / AZW / AZW3 / PRC / LIT → EPUB (Calibre) → Markdown.

Kindle (Mobipocket/KF8) and MS Reader (.lit) are proprietary binary
containers — ebooklib cannot read them. Calibre's ``ebook-convert`` turns
them into EPUB, then the pure-Python EPUB path does the text extraction.

Calibre is only needed for these formats; EPUB stays Calibre-free.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..detector import FormatName
from ..security import safe_run
from . import register, sanitize_filename
from .epub import _epub_to_text

_CALIBRE_DEFAULTS = [
    r"C:\Program Files\Calibre2\ebook-convert.exe",
    r"C:\Program Files (x86)\Calibre2\ebook-convert.exe",
    "/Applications/calibre.app/Contents/MacOS/ebook-convert",
]


def _find_ebook_convert() -> str | None:
    exe = shutil.which("ebook-convert")
    if exe:
        return exe
    return next((p for p in _CALIBRE_DEFAULTS if os.path.isfile(p)), None)


@register
class _KindleConverter:
    label = "MOBI/AZW3/LIT (Calibre → EPUB → ebooklib)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt in ("mobi", "prc", "lit")

    @staticmethod
    def check_deps() -> list[str]:
        if _find_ebook_convert():
            return []
        return [
            "Calibre ebook-convert not found (needed for MOBI/AZW3/PRC/LIT only).\n"
            "  Install: winget install calibre.calibre"
        ]

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        exe = _find_ebook_convert()
        if not exe:
            raise RuntimeError(_KindleConverter.check_deps()[0])

        with tempfile.TemporaryDirectory(prefix="mdmaker_kindle_") as tmpdir:
            epub_path = Path(tmpdir) / "book.epub"
            res = safe_run(
                [exe, str(path), str(epub_path)],
                timeout=600,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),  # no console pop-up on Windows
            )
            if res.returncode != 0 or not epub_path.exists():
                tail = (res.stderr or res.stdout or b"").decode("utf-8", "replace").strip()[-300:]
                raise RuntimeError(f"ebook-convert failed ({res.returncode}): {tail}")
            text = _epub_to_text(epub_path)

        md_path = output_dir / (sanitize_filename(path.stem) + ".md")
        md_path.write_text(
            f"# {sanitize_filename(path.stem)}\n\n"
            f"> Converted from {path.suffix.upper().lstrip('.')} via Calibre → EPUB → ebooklib\n\n"
            f"{text}",
            encoding="utf-8",
        )
        return md_path
