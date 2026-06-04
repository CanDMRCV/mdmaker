"""Tool detection v2 (Rücklauf 5: PATH-Vererbung behoben).

Beleg-Block (Rücklauf 5):
  - Anderson R2: "what you measure ≠ what you get" wenn PATH-Erbe ignoriert
  - Release It! R3: detection failure = reliability failure
  - Khorikov R3: self-test MUST use same call path as converter

URSACHE (verifiziert): subprocess.run(['tesseract','--version']) erbt den PATH
  des Elternprozesses. winget installiert in %ProgramFiles%\Tesseract-OCR\,
  was NUR im System-PATH steht (nicht im Prozess-PATH, wenn vor winget gestartet).
  → subprocess findet tesseract.exe nicht.

FIX: Absolute Pfadauflösung vor subprocess-Aufruf.
  1. Bekannte Installationsorte prüfen
  2. Windows Registry (HKLM\Software\Tesseract-OCR)
  3. shutil.which() als Fallback
  4. Gefundenen Pfad an DETEKTION und CONVERTER übergeben (Konsistenz!)

Jeder Detektor liefert (bool, str) — (installed, resolved_path_or_empty).
Der absolute Pfad wird gespeichert und an den Converter weitergereicht.
"""

import subprocess
import shutil
import os
import sys
import winreg
from pathlib import Path


def tr(s: str) -> str:
    return s


# ── A2: Robust binary resolution (filesystem first, not PATH) ──

def _resolve_tesseract() -> str:
    """Find tesseract.exe via known locations + registry. Return absolute path or ''."""
    # 1. Known install locations
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR" / "tesseract.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Tesseract-OCR" / "tesseract.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    ]
    for p in candidates:
        if p.exists():
            return str(p)

    # 2. Windows Registry
    for root in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        for subkey in [r"SOFTWARE\Tesseract-OCR", r"SOFTWARE\WOW6432Node\Tesseract-OCR"]:
            try:
                key = winreg.OpenKey(root, subkey)
                val, _ = winreg.QueryValueEx(key, "InstallDir")
                winreg.CloseKey(key)
                exe = Path(val) / "tesseract.exe"
                if exe.exists():
                    return str(exe)
            except OSError:
                pass

    # 3. shutil.which() as fallback (respects PATH of THIS process)
    found = shutil.which("tesseract")
    if found:
        return found

    return ""


def _resolve_calibre() -> str:
    """Find ebook-convert.exe."""
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Calibre2" / "ebook-convert.exe",
        Path(r"C:\Program Files\Calibre2\ebook-convert.exe"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    found = shutil.which("ebook-convert")
    return found or ""


def _resolve_7zip() -> str:
    """Find 7z.exe or 7zz.exe."""
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "7-Zip" / "7z.exe",
        Path(r"C:\Program Files\7-Zip\7z.exe"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    for cmd in ["7z", "7zz"]:
        found = shutil.which(cmd)
        if found:
            return found
    return ""


def _resolve_djvu() -> str:
    """Find djvutxt.exe."""
    candidates = [
        Path(r"C:\Program Files (x86)\DjVuLibre\djvutxt.exe"),
        Path(r"C:\Program Files\DjVuLibre\djvutxt.exe"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    found = shutil.which("djvutxt")
    return found or ""


# ── A1: Detection with resolved path (THE SAME path the converter will use) ──

def _detect_tesseract() -> tuple[bool, str]:
    """Find tesseract, then run --version with ABSOLUTE path."""
    exe = _resolve_tesseract()
    if not exe:
        return (False, "")
    try:
        result = subprocess.run(
            [exe, "--version"],
            capture_output=True, timeout=15, shell=False,
        )
        return (result.returncode == 0, exe)
    except Exception:
        return (False, exe)


def _detect_calibre() -> tuple[bool, str]:
    exe = _resolve_calibre()
    if not exe:
        return (False, "")
    try:
        result = subprocess.run(
            [exe, "--version"],
            capture_output=True, timeout=15, shell=False,
        )
        return (result.returncode == 0, exe)
    except Exception:
        return (False, exe)


def _detect_7zip() -> tuple[bool, str]:
    exe = _resolve_7zip()
    if not exe:
        return (False, "")
    try:
        result = subprocess.run(
            [exe, "--help"],
            capture_output=True, timeout=10, shell=False,
        )
        return (result.returncode == 0, exe)
    except Exception:
        return (False, exe)


def _detect_djvu() -> tuple[bool, str]:
    exe = _resolve_djvu()
    if not exe:
        return (False, "")
    try:
        result = subprocess.run(
            [exe], capture_output=True, timeout=10, shell=False,
        )
        return (b"Usage" in result.stderr or b"Usage" in result.stdout, exe)
    except Exception:
        return (False, exe)


def _detect_word_com() -> tuple[bool, str]:
    if sys.platform != "win32":
        return (False, "")
    try:
        import win32com.client
        word = win32com.client.Dispatch("Word.Application")
        word.Quit()
        return (True, "COM")
    except Exception:
        return (False, "")


def _detect_libreoffice() -> tuple[bool, str]:
    exe = shutil.which("libreoffice")
    if not exe:
        exe = str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "LibreOffice" / "program" / "soffice.exe")
        if not Path(exe).exists():
            exe = ""
    if not exe:
        return (False, "")
    try:
        result = subprocess.run([exe, "--version"], capture_output=True, timeout=15, shell=False)
        return (result.returncode == 0, exe)
    except Exception:
        return (False, exe)


def _detect_pymupdf() -> tuple[bool, str]:
    try:
        import fitz  # noqa: F401
        return (True, "import")
    except ImportError:
        return (False, "")


# ── ToolInfo class (A2: stores resolved path for converter use) ──

class ToolInfo:
    def __init__(self, key: str, name: str, formats: str,
                 detect_fn, install_cmd: str, install_note: str = "",
                 required: bool = False):
        self.key = key
        self.name = name
        self.formats = formats
        self._detect = detect_fn
        self.install_cmd = install_cmd
        self.install_note = install_note
        self.required = required
        self._resolved_path: str = ""

    def check(self) -> bool:
        """Re-run detection, cache resolved path."""
        ok, path = self._detect()
        self._resolved_path = path if ok else ""
        return ok

    def is_installed(self) -> bool:
        return self.check()

    @property
    def resolved_path(self) -> str:
        """Absolute path to the tool binary (for passing to converter)."""
        if not self._resolved_path:
            self.check()
        return self._resolved_path


# ── Registry ──

ALL_TOOLS: dict[str, ToolInfo] = {
    "pymupdf": ToolInfo("pymupdf", "PyMuPDF (fitz)", "PDF (text)",
                        _detect_pymupdf, "pip install PyMuPDF", required=True),
    "calibre": ToolInfo("calibre", "Calibre", "EPUB, MOBI, PRC",
                        _detect_calibre, "winget install calibre", required=True),
    "tesseract": ToolInfo("tesseract", "Tesseract OCR", "PDF (scanned)",
                          _detect_tesseract, "winget install tesseract-ocr.tesseract",
                          "After winget install, RESTART mdmaker — PATH update is needed for new processes.",
                          ),
    "7zip": ToolInfo("7zip", "7-Zip", "CHM",
                     _detect_7zip, "winget install 7zip.7zip"),
    "djvu": ToolInfo("djvu", "DjVuLibre", "DJVU",
                     _detect_djvu, "winget install DjVuLibre.DjView"),
    "word": ToolInfo("word", "Microsoft Word", "DOC",
                     _detect_word_com, "",
                     "Microsoft Word is part of Office/M365.",
                     ),
    "libreoffice": ToolInfo("libreoffice", "LibreOffice", "DOC",
                            _detect_libreoffice,
                            "winget install TheDocumentFoundation.LibreOffice",
                            "Free alternative to Word for .doc conversion.",
                            ),
}


def missing_tools() -> list[ToolInfo]:
    return [t for t in ALL_TOOLS.values() if not t.is_installed()]


def tools_needed_for_files(files: list[Path]) -> list[ToolInfo]:
    needed = set()
    for f in files:
        ext = f.suffix.lower()
        if ext in (".epub", ".mobi", ".prc", ".azw", ".azw3"):
            needed.add("calibre")
        elif ext == ".pdf":
            from ..detector import classify_pdf
            try:
                if classify_pdf(f) == "pdf_scan":
                    needed.add("tesseract")
                else:
                    needed.add("pymupdf")
            except Exception:
                needed.add("pymupdf")
        elif ext == ".djvu":
            needed.add("djvu")
        elif ext == ".chm":
            needed.add("7zip")
        elif ext == ".doc":
            needed.add("word")
    return [ALL_TOOLS[n] for n in needed if n in ALL_TOOLS]


def run_self_tests() -> dict:
    results = {}
    for key, t in ALL_TOOLS.items():
        try:
            ok = t.is_installed()
            results[key] = {"installed": ok, "path": t.resolved_path}
        except Exception as e:
            results[key] = {"installed": False, "path": "", "error": str(e)}
    return results
