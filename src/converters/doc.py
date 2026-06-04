"""DOC (binary OLE) → Markdown (ADR-002: tiefes Modul).

Windows: Word COM Automation — the only reliable parser for legacy .doc.
Linux/macOS: LibreOffice headless (stub in v0.1, full in v0.2).

The DocConverter interface hides platform complexity. The rest
of the system never sees Word COM or LibreOffice directly.
"""

import platform
import shutil
from pathlib import Path

from ..detector import FormatName
from ..security import safe_run
from . import Converter, register


# ── Tiefes Modul: DocConverter Interface (ADR-002) ──

class DocConverter:
    """Abstract interface for .doc conversion. Platform-specific implementations below."""

    @staticmethod
    def check_deps() -> list[str]:
        raise NotImplementedError

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        raise NotImplementedError


class WordCOMDocConverter(DocConverter):
    """Windows: Microsoft Word COM Automation.

    Quality: Perfect — native Word rendering. Requires Word installed.
    Security: Makros deaktiviert via AutomationSecurity=ForceDisable.
    """

    label = "DOC (Word COM)"

    @staticmethod
    def check_deps() -> list[str]:
        if platform.system() != "Windows":
            return ["Word COM requires Windows. On Linux/macOS, use LibreOffice."]
        try:
            import win32com.client  # noqa: F401
        except ImportError:
            return ["pywin32 not installed.\n  Fix: pip install pywin32"]
        return []

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        import win32com.client

        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        # Security: disable all macros (BRIEF_SECURITY §2)
        word.AutomationSecurity = 1  # msoAutomationSecurityForceDisable

        try:
            doc = word.Documents.Open(str(path.resolve()), ReadOnly=True)

            # Export as text
            txt_path = output_dir / (path.stem + ".txt")
            doc.SaveAs(str(txt_path), FileFormat=7)  # wdFormatText

            doc.Close()
        finally:
            word.Quit()

        # TXT → MD
        raw = txt_path.read_text(encoding="utf-8", errors="replace")
        md_path = output_dir / (path.stem + ".md")
        md_path.write_text(
            f"# {path.stem}\n\n> Converted from DOC via Word COM\n\n{raw}",
            encoding="utf-8",
        )
        txt_path.unlink(missing_ok=True)
        return md_path


class LibreOfficeDocConverter(DocConverter):
    """Linux/macOS: LibreOffice --headless (STUB in v0.1).

    Will be implemented in v0.2 with:
        libreoffice --headless --convert-to txt <file> --outdir <dir>
    """

    label = "DOC (LibreOffice — stub)"

    @staticmethod
    def check_deps() -> list[str]:
        if platform.system() == "Windows":
            return []  # Word COM is available, LibreOffice not needed
        if shutil.which("libreoffice") is None:
            return [
                "LibreOffice not found.\n"
                "  Install: https://www.libreoffice.org/download/\n"
                "  Or pre-convert .doc to .docx with another tool."
            ]
        return []

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        if platform.system() == "Windows":
            # Delegate to Word COM
            return WordCOMDocConverter.convert(path, output_dir)

        # Linux/macOS: stub — clear error message
        raise NotImplementedError(
            "DOC conversion on Linux/macOS requires LibreOffice (planned v0.2).\n"
            "For now, pre-convert .doc to .docx using: "
            "libreoffice --headless --convert-to docx " + str(path)
        )


# ── Registry Entry ──

@register
class _DocRegistryAdapter:
    """Adapter that routes to the platform-appropriate DocConverter."""

    label = "DOC (Word COM / LibreOffice)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt == "doc"

    @staticmethod
    def check_deps() -> list[str]:
        return WordCOMDocConverter.check_deps() + LibreOfficeDocConverter.check_deps()

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        if platform.system() == "Windows":
            return WordCOMDocConverter.convert(path, output_dir)
        return LibreOfficeDocConverter.convert(path, output_dir)
