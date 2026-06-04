"""EPUB / MOBI / PRC → Markdown via Calibre ebook-convert (ADR-001).

Why Calibre: MarkItDown fails on Python 3.14 (magika dependency) and
parses EPUB as ZIP → outputs CSS/XML, not text. Calibre's EPUB parser
extracts actual text content from HTML inside the container.

MOBI/PRC route: Calibre → EPUB → TXT → MD (two-hop for MOBI).
"""

import shutil
from pathlib import Path

from ..detector import FormatName
from ..security import safe_run
from . import Converter, register


@register
class _EpubConverter:
    label = "EPUB/MOBI/PRC (Calibre)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt in ("epub", "mobi", "prc")

    @staticmethod
    def check_deps() -> list[str]:
        if shutil.which("ebook-convert") is None:
            return [
                "Calibre ebook-convert not found.\n"
                "  Install: winget install calibre\n"
                "  Or:      https://calibre-ebook.com/download"
            ]
        return []

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        work_path = path

        # Step 1: MOBI/PRC → EPUB (Calibre does this natively)
        if path.suffix.lower() in (".mobi", ".prc", ".azw", ".azw3"):
            epub_path = output_dir / (path.stem + ".epub")
            if not epub_path.exists():
                safe_run(
                    ["ebook-convert", str(path), str(epub_path)],
                    timeout=300,
                )
            work_path = epub_path

        # Step 2: EPUB → TXT via Calibre
        txt_path = output_dir / (path.stem + ".txt")
        safe_run(
            ["ebook-convert", str(work_path), str(txt_path)],
            timeout=300,
            check=True,
        )

        # Step 3: TXT → MD
        md_path = output_dir / (path.stem + ".md")
        raw = txt_path.read_text(encoding="utf-8", errors="replace")
        title = path.stem
        md_path.write_text(
            f"# {title}\n\n> Converted from {path.suffix.upper().lstrip('.')} via Calibre\n\n{raw}",
            encoding="utf-8",
        )

        txt_path.unlink(missing_ok=True)
        return md_path
