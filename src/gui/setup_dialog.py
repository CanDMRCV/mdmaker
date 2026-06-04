"""First-Run Setup Dialog (B1) + Pre-Run Check Dialog (B2).

A1: On first launch, checks all external tools, offers install per tool.
     NIE still installieren — jeder Install-Knopf braucht expliziten Klick.
A2: Before each run, checks which tools the SELECTED files need.
     Offers: Install / Start anyway (these will fail) / Cancel.

Security-Gate: Installation nur mit Zustimmung. Kein winget ohne Nutzer-Klick.
"""

import subprocess
import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QCheckBox, QDialogButtonBox, QGroupBox, QFrame, QMessageBox,
    QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ..pipeline import collect_files, check_all_dependencies
from ..detector import classify_pdf


def tr(s: str) -> str:
    return s


# ── Tool Registry ──

class ToolInfo:
    def __init__(self, name: str, formats: str, check_paths: list[str],
                 check_exe: str, install_cmd: str, required: bool = False):
        self.name = name
        self.formats = formats
        self.check_paths = check_paths
        self.check_exe = check_exe
        self.install_cmd = install_cmd
        self.required = required

    def is_installed(self) -> bool:
        if shutil.which(self.check_exe):
            return True
        for p in self.check_paths:
            if Path(p).exists():
                return True
        return False


TOOLS: dict[str, ToolInfo] = {
    "PyMuPDF": ToolInfo(
        "PyMuPDF (fitz)", "PDF (text) — fast extraction",
        [], "fitz",  # Python import
        "pip install PyMuPDF", required=True,
    ),
    "Calibre": ToolInfo(
        "Calibre", "EPUB, MOBI, PRC",
        [], "ebook-convert",
        "winget install calibre", required=True,
    ),
    "Tesseract": ToolInfo(
        "Tesseract OCR", "PDF (scanned) — optical character recognition",
        [r"C:\Program Files\Tesseract-OCR\tesseract.exe",
         r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"],
        "tesseract",
        "winget install tesseract-ocr.tesseract", required=False,
    ),
    "DjVuLibre": ToolInfo(
        "DjVuLibre", "DJVU",
        [r"C:\Program Files (x86)\DjVuLibre\djvutxt.exe",
         r"C:\Program Files\DjVuLibre\djvutxt.exe"],
        "djvutxt",
        "winget install DjVuLibre.DjView", required=False,
    ),
    "7-Zip": ToolInfo(
        "7-Zip", "CHM (compiled HTML help)",
        [r"C:\Program Files\7-Zip\7z.exe"],
        "7z",
        "winget install 7zip.7zip", required=False,
    ),
    "Word/LibreOffice": ToolInfo(
        "Word or LibreOffice", "DOC (legacy Word)",
        [r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
         r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE"],
        "winword",
        "Install Microsoft Word or LibreOffice", required=False,
    ),
}


def _check_pymupdf() -> bool:
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def missing_tools() -> list[ToolInfo]:
    """Return list of tools that are NOT installed."""
    missing = []
    for t in TOOLS.values():
        if t.check_exe == "fitz":
            if not _check_pymupdf():
                missing.append(t)
        elif not t.is_installed():
            missing.append(t)
    return missing


def tools_needed_for_files(files: list[Path]) -> list[ToolInfo]:
    """Which tools do these specific files need?"""
    needed = set()
    for f in files:
        ext = f.suffix.lower()
        if ext in (".epub", ".mobi", ".prc", ".azw", ".azw3"):
            needed.add("Calibre")
        elif ext == ".pdf":
            try:
                if classify_pdf(f) == "pdf_scan":
                    needed.add("Tesseract")
                else:
                    needed.add("PyMuPDF")
            except Exception:
                needed.add("PyMuPDF")
        elif ext == ".djvu":
            needed.add("DjVuLibre")
        elif ext == ".chm":
            needed.add("7-Zip")
        elif ext == ".doc":
            needed.add("Word/LibreOffice")

    return [TOOLS[n] for n in needed if n in TOOLS]


# ── A1: First-Run Setup Dialog ──

class SetupDialog(QDialog):
    """First-run: shows tool status, offers install per tool.

    Security: NEVER auto-installs. Every install needs explicit button press.
    Uses 'winget' with user consent — tooltip shows exact command.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("mdmaker — Setup"))
        self.setMinimumSize(600, 450)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel(tr("Welcome to mdmaker!"))
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(title)

        layout.addWidget(QLabel(
            tr("mdmaker needs some external tools for certain e-book formats. "
               "Let's check what's installed and set up what's missing.")))
        layout.addWidget(QLabel(
            tr("No tool will be installed without your explicit click. "
               "All processing stays on your computer.")))

        # Tool list
        tools_group = QGroupBox(tr("External Tools"))
        tools_layout = QVBoxLayout(tools_group)

        self._tool_widgets = {}
        for name, t in TOOLS.items():
            row = QHBoxLayout()
            installed = t.is_installed() if t.check_exe != "fitz" else _check_pymupdf()

            icon = "✅" if installed else "❌"
            label = QLabel(f"{icon}  {t.name}")
            label.setToolTip(tr(f"Needed for: {t.formats}"))
            row.addWidget(label, 1)

            if installed:
                row.addWidget(QLabel(tr("Installed")), 0)
            else:
                btn = QPushButton(tr("Install"))
                btn.setToolTip(t.install_cmd)
                btn.setStyleSheet(
                    "QPushButton { background-color: #0d6efd; color: white; "
                    "padding: 4px 12px; border-radius: 3px; }"
                    "QPushButton:hover { background-color: #0b5ed7; }"
                )
                btn.clicked.connect(lambda checked, ti=t: self._install_tool(ti))
                row.addWidget(btn, 0)

            tools_layout.addLayout(row)
            self._tool_widgets[name] = {"installed": installed, "row": row}

        layout.addWidget(tools_group)

        # Buttons
        btn_box = QDialogButtonBox()
        self._skip_btn = btn_box.addButton(
            tr("Skip — I'll set up later"), QDialogButtonBox.RejectRole)
        self._done_btn = btn_box.addButton(
            tr("Continue"), QDialogButtonBox.AcceptRole)
        self._done_btn.setStyleSheet(
            "QPushButton { background-color: #198754; color: white; padding: 6px 20px; "
            "font-weight: bold; border-radius: 4px; }")
        layout.addWidget(btn_box)

        self._skip_btn.clicked.connect(self.reject)
        self._done_btn.clicked.connect(self.accept)

    def _install_tool(self, tool: ToolInfo):
        """Run winget install with user consent dialog."""
        msg = tr(
            f"mdmaker will now run:\n\n"
            f"  {tool.install_cmd}\n\n"
            f"This installs {tool.name} for {tool.formats}.\n"
            f"Continue?"
        )
        reply = QMessageBox.question(
            self, tr("Install tool?"), msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply != QMessageBox.Yes:
            return

        # Run winget
        try:
            subprocess.Popen(
                tool.install_cmd.split(),
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
        except Exception:
            QMessageBox.information(
                self, tr("Manual install needed"),
                tr(f"Could not run installer automatically.\n\n"
                   f"Please run this command manually:\n{tool.install_cmd}"))

    def tools_still_missing(self) -> list[ToolInfo]:
        """After dialog closes, which required tools are still missing?"""
        return [t for t in missing_tools() if t.required]


# ── A2: Pre-Run Check Dialog ──

class PreRunCheckDialog(QDialog):
    """Before each run: check needed tools for selected files.

    Offers: Install / Start anyway (these will fail) / Cancel
    """

    def __init__(self, files: list[Path], parent=None):
        super().__init__(parent)
        self.files = files
        self._continue_anyway = False
        self.setWindowTitle(tr("mdmaker — Pre-Run Check"))
        self.setMinimumSize(500, 300)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel(
            tr(f"About to convert {len(self.files)} file(s).")))

        needed = tools_needed_for_files(self.files)
        missing_needed = [t for t in needed if not t.is_installed()
                          if t.check_exe != "fitz" or not _check_pymupdf()]

        if not missing_needed:
            layout.addWidget(QLabel("✅ " + tr("All needed tools are installed.")))
            btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
            btn_box.accepted.connect(self.accept)
            layout.addWidget(btn_box)
            return

        layout.addWidget(QLabel(
            tr("⚠ Some files need tools that are not installed:")))

        for t in missing_needed:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"  ❌ {t.name} — needed for: {t.formats}"))
            btn = QPushButton(tr("Install"))
            btn.setToolTip(t.install_cmd)
            btn.setStyleSheet(
                "QPushButton { background-color: #0d6efd; color: white; "
                "padding: 4px 12px; border-radius: 3px; }")
            btn.clicked.connect(lambda checked, ti=t, parent=self:
                                self._install_and_refresh(ti))
            row.addWidget(btn)
            layout.addLayout(row)

        layout.addWidget(QLabel(
            tr("Files that need missing tools will FAIL. "
               "You can install them now, or continue anyway.")))

        # Buttons
        btn_box = QDialogButtonBox()
        cancel_btn = btn_box.addButton(tr("Cancel"), QDialogButtonBox.RejectRole)
        continue_btn = btn_box.addButton(
            tr("Continue anyway (some will fail)"), QDialogButtonBox.AcceptRole)
        continue_btn.setStyleSheet("color: #dc3545;")
        btn_box.addButton(continue_btn)
        layout.addWidget(btn_box)

        cancel_btn.clicked.connect(self.reject)
        continue_btn.clicked.connect(self._continue)

    def _install_and_refresh(self, tool: ToolInfo):
        """Install a tool, then re-check. Same consent flow as SetupDialog."""
        dlg = SetupDialog(self)  # Reuse install flow
        dlg.exec()

    def _continue(self):
        self._continue_anyway = True
        self.accept()

    @property
    def continue_anyway(self) -> bool:
        return self._continue_anyway
