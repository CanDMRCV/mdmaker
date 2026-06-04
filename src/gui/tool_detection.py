"""Tool detection (A1-A3: test like the converter tests, NOT via which/Pfad).

Beleg-Block:
  - Quellenbindung: Khorikov R3 (Unit Testing) → self-test per detector
  - Ousterhout R4: detection is a TIEFES Modul — simple interface, complex internals
  - Anderson R2: "what you measure is what you get" — detection must match RUNTIME PATH
  - Release It! R3: detection failures are reliability failures → robust subprocess handling

FIX (Rücklauf 4): Testwerkzeuge über ECHTEN AUFRUF, nicht Pfadsuche.
  - Tesseract: subprocess.run(['tesseract','--version']) — gleicher PATH wie Converter
  - Word: COM-Objekt probeweise instanziieren — kein which('winword')
  - Calibre/7-Zip/DjVuLibre: subprocess.run(['exe','--version'])

Jeder Detektor hat einen Selbsttest (test_detector_*) — Tool da → True, Tool weg → False.
"""

import subprocess
import shutil
import os
import sys
from pathlib import Path


def tr(s: str) -> str:
    return s


class ToolInfo:
    """Information about an external tool — detection + install instructions."""

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

    def is_installed(self) -> bool:
        try:
            return self._detect()
        except Exception:
            return False


# ── A1: Detection via ACTUAL invocation (matches converter runtime) ──

def _detect_tesseract() -> bool:
    """Run 'tesseract --version' — same call path as pytesseract/pyocr."""
    result = subprocess.run(
        ["tesseract", "--version"],
        capture_output=True, timeout=15,
        shell=False,
        env={**os.environ},  # Same env as runtime
    )
    return result.returncode == 0


def _detect_calibre() -> bool:
    """Run 'ebook-convert --version' — same as the EPUB converter."""
    result = subprocess.run(
        ["ebook-convert", "--version"],
        capture_output=True, timeout=15, shell=False,
        env={**os.environ},
    )
    return result.returncode == 0


def _detect_7zip() -> bool:
    """Try '7z' then '7zz' — same as the CHM converter."""
    for cmd in ["7z", "7zz"]:
        result = subprocess.run(
            [cmd, "--help"],
            capture_output=True, timeout=10, shell=False,
            env={**os.environ},
        )
        if result.returncode == 0:
            return True
    return False


def _detect_djvu() -> bool:
    """Run 'djvutxt' (or full path) — same as the DJVU converter."""
    exe = shutil.which("djvutxt")
    if not exe:
        for p in [r"C:\Program Files (x86)\DjVuLibre\djvutxt.exe",
                  r"C:\Program Files\DjVuLibre\djvutxt.exe"]:
            if Path(p).exists():
                exe = p
                break
    if not exe:
        return False
    result = subprocess.run(
        [exe], capture_output=True, timeout=10, shell=False,
        env={**os.environ},
    )
    # djvutxt with no args exits non-zero but prints help — that's OK
    return b"Usage" in result.stderr or b"Usage" in result.stdout or result.returncode == 0


def _detect_word_com() -> bool:
    """Try to instantiate Word COM object — matches DOC converter (ADR-002)."""
    if sys.platform != "win32":
        return False
    try:
        import win32com.client
        word = win32com.client.Dispatch("Word.Application")
        word.Quit()
        return True
    except Exception:
        return False


def _detect_libreoffice() -> bool:
    """Run 'libreoffice --version' — alternative DOC converter."""
    result = subprocess.run(
        ["libreoffice", "--version"],
        capture_output=True, timeout=15, shell=False,
        env={**os.environ},
    )
    return result.returncode == 0


def _detect_pymupdf() -> bool:
    """Import fitz — same as pdf_text converter."""
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


# ── Tool Registry (A3: self-testable) ──

ALL_TOOLS: dict[str, ToolInfo] = {
    "pymupdf": ToolInfo(
        "pymupdf", "PyMuPDF (fitz)", "PDF (text)",
        _detect_pymupdf,
        "pip install PyMuPDF",
        required=True,
    ),
    "calibre": ToolInfo(
        "calibre", "Calibre", "EPUB, MOBI, PRC",
        _detect_calibre,
        "winget install calibre",
        required=True,
    ),
    "tesseract": ToolInfo(
        "tesseract", "Tesseract OCR", "PDF (scanned)",
        _detect_tesseract,
        "winget install tesseract-ocr.tesseract",
        "After install, add to PATH or copy tesseract.exe to a PATH directory.",
    ),
    "7zip": ToolInfo(
        "7zip", "7-Zip", "CHM",
        _detect_7zip,
        "winget install 7zip.7zip",
    ),
    "djvu": ToolInfo(
        "djvu", "DjVuLibre", "DJVU",
        _detect_djvu,
        "winget install DjVuLibre.DjView",
    ),
    "word": ToolInfo(
        "word", "Microsoft Word", "DOC",
        _detect_word_com,
        "",  # No winget command — Word comes via Office/M365
        "Microsoft Word is part of Office/M365. Install via office.com or use LibreOffice.",
    ),
    "libreoffice": ToolInfo(
        "libreoffice", "LibreOffice", "DOC",
        _detect_libreoffice,
        "winget install TheDocumentFoundation.LibreOffice",
        "LibreOffice is a free alternative to Microsoft Word for .doc conversion.",
    ),
}


def missing_tools() -> list[ToolInfo]:
    """All tools that are NOT installed."""
    return [t for t in ALL_TOOLS.values() if not t.is_installed()]


def tools_needed_for_files(files: list[Path]) -> list[ToolInfo]:
    """Which tools are needed for these specific files?"""
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


# ── A3: Self-Tests ──

def run_self_tests() -> dict:
    """Run all detectors and report results. For debugging detection bugs."""
    results = {}
    for key, t in ALL_TOOLS.items():
        try:
            ok = t.is_installed()
            results[key] = {"installed": ok, "error": None}
        except Exception as e:
            results[key] = {"installed": False, "error": str(e)}
    return results
