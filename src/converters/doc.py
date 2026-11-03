"""Old .doc (Word 97-2003) → Markdown via multiple backends.

Tries backends in order of preference (no terminal windows first):
    1. LibreOffice headless — faster, no GUI, cross-platform
    2. Word COM — Windows-only, reliable for complex .doc files
    3. python-docx fallback — works if the file is actually .docx renamed

CRITICAL: All subprocess calls use CREATE_NO_WINDOW (0x08000000) to prevent
terminal popups on Windows. LibreOffice gets extra flags (--invisible,
--norestore) to suppress any GUI element.
"""

import subprocess
import os
import shutil
from pathlib import Path

from ..detector import FormatName
from . import Converter, register

# Windows-only flag: prevent ANY window from appearing
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _find_libreoffice() -> str | None:
    """Find LibreOffice soffice.exe on the system."""
    for name in ["soffice", "soffice.exe", "libreoffice"]:
        found = shutil.which(name)
        if found:
            return found
    for base in [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]:
        if Path(base).exists():
            return base
    return None


@register
class _DocConverter:
    label = "DOC (LibreOffice / Word COM / python-docx)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt == "doc"

    @staticmethod
    def check_deps() -> list[str]:
        if os.name != "nt":
            if _find_libreoffice() is None:
                return [
                    "LibreOffice not found.\n"
                    "  Install:  sudo apt install libreoffice  (Linux)\n"
                    "  Or:       brew install libreoffice      (macOS)"
                ]
            return []
        if _find_libreoffice() is not None:
            return []
        return []

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        txt_path = output_dir / (path.stem + ".txt")
        errors = []

        # Backend 1: LibreOffice headless — extra flags to prevent ANY GUI
        lo_exe = _find_libreoffice()
        if lo_exe is not None:
            try:
                # Build isolated profile dir to avoid locking user's running LO
                import tempfile
                lo_profile = tempfile.mkdtemp(prefix="mdmaker_lo_")
                env = os.environ.copy()
                subprocess.run(
                    [
                        lo_exe,
                        "-env:UserInstallation=file://" + lo_profile.replace("\\", "/"),
                        "--headless",
                        "--invisible",
                        "--norestore",
                        "--nofirststartwizard",
                        "--convert-to", "txt:Text",
                        "--outdir", str(output_dir),
                        str(path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=True,
                    creationflags=CREATE_NO_WINDOW,
                    env=env,
                )
                # Cleanup temp profile
                try:
                    shutil.rmtree(lo_profile, ignore_errors=True)
                except Exception:
                    pass

                lo_txt = output_dir / (path.stem + ".txt")
                if not lo_txt.exists():
                    alt_txt = output_dir / (path.name + ".txt")
                    if alt_txt.exists():
                        alt_txt.rename(lo_txt)
                if lo_txt.exists():
                    raw = lo_txt.read_text(encoding="utf-8", errors="replace")
                    md_path = output_dir / (path.stem + ".md")
                    md_path.write_text(
                        f"# {path.stem}\n\n> Converted via LibreOffice headless\n\n{raw}",
                        encoding="utf-8",
                    )
                    lo_txt.unlink(missing_ok=True)
                    return md_path
            except Exception as e:
                errors.append(f"LibreOffice: {e}")

        # Backend 2: Word COM (Windows only, hidden window)
        if os.name == "nt":
            try:
                script = f"""
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$doc = $word.Documents.Open('{path}', $false, $true)
$txtPath = '{txt_path}'
$doc.SaveAs($txtPath, 7)
$doc.Close()
$word.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
"""
                subprocess.run(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    creationflags=CREATE_NO_WINDOW,
                )
                if txt_path.exists():
                    raw = txt_path.read_text(encoding="utf-8", errors="replace")
                    md_path = output_dir / (path.stem + ".md")
                    md_path.write_text(
                        f"# {path.stem}\n\n> Converted via Word COM\n\n{raw}",
                        encoding="utf-8",
                    )
                    txt_path.unlink(missing_ok=True)
                    return md_path
            except Exception as e:
                errors.append(f"Word COM: {e}")

        # Backend 3: Try python-docx (some .doc files are actually .docx)
        try:
            from docx import Document
            doc = Document(str(path))
            paragraphs = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    paragraphs.append("")
                    continue
                if para.style.name.startswith("Heading"):
                    level = int(para.style.name.split()[-1]) if para.style.name.split()[-1].isdigit() else 1
                    paragraphs.append(f"{'#' * min(level, 6)} {text}")
                else:
                    paragraphs.append(text)
            md_path = output_dir / (path.stem + ".md")
            md_path.write_text(
                f"# {path.stem}\n\n> Converted via python-docx (treated as .docx)\n\n"
                + "\n\n".join(paragraphs),
                encoding="utf-8",
            )
            return md_path
        except Exception as e:
            errors.append(f"python-docx: {e}")

        raise RuntimeError(
            f"All DOC conversion backends failed for {path.name}:\n"
            + "\n".join(f"  {e}" for e in errors)
            + "\n\n  Install LibreOffice:  winget install LibreOffice.LibreOffice"
        )
