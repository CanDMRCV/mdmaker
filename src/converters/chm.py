"""CHM (Compiled HTML Help) → Markdown via 7-Zip (ADR-004).

CHM = Microsoft ITFS container with embedded HTML files.
7-Zip handles the ITFS format natively and cross-platform.
Extract → parse HTML → plain text → Markdown.
"""

import re
import shutil
import tempfile
from pathlib import Path

from ..detector import FormatName
from ..security import safe_run
from . import Converter, register


@register
class _ChmConverter:
    label = "CHM (7z extract + HTML→text)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt == "chm"

    @staticmethod
    def check_deps() -> list[str]:
        for cmd in ["7z", "7zz"]:
            if shutil.which(cmd):
                return []
        # Fallback: Windows hh.exe
        if Path(r"C:\Windows\hh.exe").exists():
            return []
        return [
            "7-Zip not found (needed for CHM extraction).\n"
            "  Install: winget install 7zip.7zip"
        ]

    @staticmethod
    def _find_extractor() -> tuple[str, list[str]]:
        for cmd in ["7z", "7zz"]:
            exe = shutil.which(cmd)
            if exe:
                return exe, ["x", "-y"]
        return r"C:\Windows\hh.exe", ["-decompile"]

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        exe, base_args = _ChmConverter._find_extractor()

        with tempfile.TemporaryDirectory(prefix="mdmaker_chm_") as tmpdir:
            tmp = Path(tmpdir)

            if "decompile" in base_args:
                safe_run([exe, "-decompile", str(tmp), str(path)], timeout=120)
            else:
                safe_run([exe] + base_args + [str(path), f"-o{tmp}"], timeout=120)

            # Collect and parse HTML
            html_files = sorted(tmp.rglob("*.htm*"))
            if not html_files:
                raise FileNotFoundError(f"No HTML extracted from {path.name}")

            parts = []
            total_chars = 0

            for hf in html_files:
                try:
                    raw = hf.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    try:
                        raw = hf.read_text(encoding="cp1252", errors="replace")
                    except Exception:
                        continue

                # Strip scripts, styles
                raw = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL | re.IGNORECASE)
                raw = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL | re.IGNORECASE)
                # Block elements → newlines
                raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.IGNORECASE)
                raw = re.sub(r'</?(?:p|div|h[1-6]|li|tr|table)[^>]*>', '\n', raw, flags=re.IGNORECASE)
                # Strip remaining tags
                raw = re.sub(r'<[^>]+>', '', raw)
                # Entities
                for entity, char in [('&nbsp;',' '),('&amp;','&'),('&lt;','<'),('&gt;','>'),('&quot;','"')]:
                    raw = raw.replace(entity, char)
                # Collapse whitespace
                raw = re.sub(r'\n\s*\n', '\n\n', raw)
                raw = re.sub(r'[ \t]+', ' ', raw).strip()

                if raw:
                    parts.append(f"## {hf.stem}\n\n{raw}\n")
                    total_chars += len(raw)

        if total_chars == 0:
            raise ValueError(f"No text extracted from {path.name}")

        md_path = output_dir / (path.stem + ".md")
        header = (
            f"# {path.stem}\n\n"
            f"> {len(html_files)} HTML files · {total_chars:,} chars · "
            f"Converted from CHM via {'7z' if '7' in exe else 'hh.exe'}\n\n"
        )
        md_path.write_text(header + "\n".join(parts), encoding="utf-8")
        return md_path
