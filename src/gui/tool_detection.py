r"""Tool detection v3 — file-existence only, NO subprocess calls.

CRITICAL: Detection must NEVER run external binaries. Reasons:
  1. LibreOffice (and some other tools) flash a terminal window even with
     CREATE_NO_WINDOW — the flag is a request, not a guarantee.
  2. Each subprocess.run([exe, "--version"]) takes 1–15 seconds, freezing
     the Qt event loop during PreRunCheckDialog (modal).
  3. File-existence check is instant, reliable, and sufficient.

Verification (that the binary actually works) happens at conversion time,
where proper CREATE_NO_WINDOW + --headless flags are applied.

Beleg-Block (Rücklauf 6):
  - Khorikov R3: detection must not block the UI thread
  - Anderson R2: what you measure ≠ what you get when detection has side effects
"""

import os
import sys
import shutil
import winreg
from pathlib import Path


def tr(s: str) -> str:
    return s


# ── Cache: detect once, never re-run ──
_cache: dict[str, tuple[bool, str]] = {}


def _cached(key: str, fn) -> tuple[bool, str]:
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def _clear_cache():
    _cache.clear()


# ── Resolution: find binary by filesystem + registry, NEVER run it ──

def _resolve_tesseract() -> str:
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR" / "tesseract.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Tesseract-OCR" / "tesseract.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
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
    found = shutil.which("tesseract")
    return found or ""


def _resolve_calibre() -> str:
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
    candidates = [
        Path(r"C:\Program Files (x86)\DjVuLibre\djvutxt.exe"),
        Path(r"C:\Program Files\DjVuLibre\djvutxt.exe"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    found = shutil.which("djvutxt")
    return found or ""


# ── Detection: file-existence ONLY, no subprocess ──

def _detect_tesseract() -> tuple[bool, str]:
    return _cached("tesseract", lambda: (
        bool(_resolve_tesseract()), _resolve_tesseract()
    ))


def _detect_calibre() -> tuple[bool, str]:
    return _cached("calibre", lambda: (
        bool(_resolve_calibre()), _resolve_calibre()
    ))


def _detect_7zip() -> tuple[bool, str]:
    return _cached("7zip", lambda: (
        bool(_resolve_7zip()), _resolve_7zip()
    ))


def _detect_djvu() -> tuple[bool, str]:
    return _cached("djvu", lambda: (
        bool(_resolve_djvu()), _resolve_djvu()
    ))


def _detect_word_com() -> tuple[bool, str]:
    if sys.platform != "win32":
        return _cached("word_com", lambda: (False, ""))
    return _cached("word_com", lambda: (
        bool(shutil.which("winword")) or
        Path(r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE").exists() or
        Path(r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE").exists(),
        "COM" if True else ""
    ))


def _detect_libreoffice() -> tuple[bool, str]:
    return _cached("libreoffice", lambda: (
        bool(_find_libreoffice_exe()), _find_libreoffice_exe()
    ))


def _find_libreoffice_exe() -> str:
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
    return ""


def _detect_pymupdf() -> tuple[bool, str]:
    return _cached("pymupdf", lambda: (
        _check_import("pymupdf"), "import"
    ))


def _detect_ebooklib() -> tuple[bool, str]:
    return _cached("ebooklib", lambda: (
        _check_import("ebooklib") and _check_import("bs4"), "import"
    ))


def _check_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


# ── ToolInfo class ──

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
        ok, path = self._detect()
        self._resolved_path = path if ok else ""
        return ok

    def is_installed(self) -> bool:
        return self.check()

    @property
    def resolved_path(self) -> str:
        if not self._resolved_path:
            self.check()
        return self._resolved_path


# ── Registry ──

ALL_TOOLS: dict[str, ToolInfo] = {
    "pymupdf": ToolInfo("pymupdf", "PyMuPDF (fitz)", "PDF (text)",
                        _detect_pymupdf, "pip install PyMuPDF", required=True),
    "ebooklib": ToolInfo("ebooklib", "ebooklib + bs4", "EPUB, MOBI, PRC",
                         _detect_ebooklib, "pip install ebooklib beautifulsoup4 lxml", required=True),
    "tesseract": ToolInfo("tesseract", "Tesseract OCR", "PDF (scanned)",
                          _detect_tesseract, "winget install tesseract-ocr.tesseract",
                          "Also download eng.traineddata from tessdata repo."),
    "7zip": ToolInfo("7zip", "7-Zip", "CHM",
                     _detect_7zip, "winget install 7zip.7zip"),
    "djvu": ToolInfo("djvu", "DjVuLibre", "DJVU",
                     _detect_djvu, "winget install DjVuLibre.DjView"),
    "word": ToolInfo("word", "Microsoft Word", "DOC",
                     _detect_word_com, "",
                     "Microsoft Word is part of Office/M365."),
    "libreoffice": ToolInfo("libreoffice", "LibreOffice", "DOC",
                            _detect_libreoffice,
                            "winget install TheDocumentFoundation.LibreOffice",
                            "Free alternative to Word for .doc conversion."),
}


def missing_tools() -> list[ToolInfo]:
    return [t for t in ALL_TOOLS.values() if not t.is_installed()]


def tools_needed_for_files(files: list[Path]) -> list[ToolInfo]:
    needed = set()
    for f in files:
        from ..detector import detect_format
        fmt = detect_format(f)
        if fmt in ("epub", "mobi", "prc"):
            needed.add("ebooklib")
        elif fmt == "pdf_text":
            needed.add("pymupdf")
        elif fmt == "pdf_scan":
            needed.add("tesseract")
        elif fmt == "djvu":
            needed.add("djvu")
        elif fmt == "chm":
            needed.add("7zip")
        elif fmt == "doc":
            if not _detect_libreoffice()[0]:
                needed.add("word")
        elif fmt == "docx":
            pass
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
