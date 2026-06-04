"""DJVU → Markdown via DjVuLibre djvutxt.

DjVuLibre is the reference implementation for DJVU. djvutxt extracts
the hidden text layer (most DJVU files are OCR'd scans with text layer).
No OCR needed — text is already embedded.
"""

import shutil
from pathlib import Path

from ..detector import FormatName
from ..security import safe_run
from . import Converter, register


@register
class _DjvuConverter:
    label = "DJVU (DjVuLibre)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt == "djvu"

    @staticmethod
    def check_deps() -> list[str]:
        if shutil.which("djvutxt"):
            return []
        # Check common Windows install paths
        for p in [
            Path(r"C:\Program Files (x86)\DjVuLibre\djvutxt.exe"),
            Path(r"C:\Program Files\DjVuLibre\djvutxt.exe"),
        ]:
            if p.exists():
                return []
        return [
            "DjVuLibre djvutxt not found.\n"
            "  Install: winget install DjVuLibre.DjView\n"
            "  Or:      https://djvu.sourceforge.net/"
        ]

    @staticmethod
    def _find_djvutxt() -> str:
        which = shutil.which("djvutxt")
        if which:
            return which
        for p in [
            r"C:\Program Files (x86)\DjVuLibre\djvutxt.exe",
            r"C:\Program Files\DjVuLibre\djvutxt.exe",
        ]:
            if Path(p).exists():
                return p
        return "djvutxt"  # Hope it's on PATH

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        djvutxt = _DjvuConverter._find_djvutxt()
        txt_path = output_dir / (path.stem + ".txt")

        safe_run(
            [djvutxt, str(path), str(txt_path)],
            timeout=300,
            check=True,
        )

        if not txt_path.exists():
            raise FileNotFoundError(f"djvutxt output missing: {txt_path}")

        raw = txt_path.read_text(encoding="utf-8", errors="replace")
        md_path = output_dir / (path.stem + ".md")
        md_path.write_text(
            f"# {path.stem}\n\n> Converted via DjVuLibre djvutxt\n\n{raw}",
            encoding="utf-8",
        )
        txt_path.unlink(missing_ok=True)
        return md_path
