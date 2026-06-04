"""Setup + PreRunCheck Dialogs (v0.3.2 — uses tool_detection for accurate checks).

A1: First-Run Setup — checks all tools via ECHTEM Aufruf, offers install per tool.
     NIE still installieren. Jeder Install-Knopf braucht expliziten Klick.
A2: Pre-Run Check — vor jedem Lauf: tools_needed_for_files() prüfen.
     Install / Trotzdem starten / Abbrechen.

Beleg-Block (Rücklauf 4):
  - Detection now uses subprocess.run() for CLI tools (same PATH as converter)
  - Word: COM-Objekt probeweise instanziieren (win32com)
  - PATH-Konsistenz: os.environ passed to subprocess = same env as runtime
"""

import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QDialogButtonBox, QGroupBox, QMessageBox, QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from .tool_detection import (
    ALL_TOOLS, ToolInfo, missing_tools, tools_needed_for_files, tr,
)


class SetupDialog(QDialog):
    """First-run: shows tool status, offers install per tool.

    Security: NEVER auto-installs. Every install needs explicit button press.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("mdmaker — Setup"))
        self.setMinimumSize(600, 480)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        title = QLabel(tr("Welcome to mdmaker!"))
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(title)

        layout.addWidget(QLabel(
            tr("mdmaker needs some external tools for certain e-book formats. "
               "Let's check what's installed.")))
        layout.addWidget(QLabel(
            tr("No tool will be installed without your explicit click. "
               "All processing stays on your computer.")))

        tools_group = QGroupBox(tr("External Tools"))
        tools_layout = QVBoxLayout(tools_group)

        for t in ALL_TOOLS.values():
            row = QHBoxLayout()
            installed = t.is_installed()

            icon = "✅" if installed else "❌"
            label = QLabel(f"{icon}  {t.name}")
            label.setToolTip(tr(f"Needed for: {t.formats}"))
            row.addWidget(label, 1)

            if installed:
                row.addWidget(QLabel(tr("Ready")), 0)
            else:
                cmd = t.install_cmd
                if cmd:
                    copy_btn = QPushButton(tr("📋 Copy command"))
                    copy_btn.setToolTip(cmd)
                    copy_btn.setStyleSheet(
                        "QPushButton { font-size: 8pt; padding: 2px 8px; }")
                    copy_btn.clicked.connect(
                        lambda checked, c=cmd: QApplication.clipboard().setText(c))
                    row.addWidget(copy_btn, 0)
                if t.install_note:
                    note = QLabel(t.install_note[:70])
                    note.setWordWrap(True)
                    note.setStyleSheet("color: #6c757d; font-size: 8pt;")
                    row.addWidget(note, 2)

            tools_layout.addLayout(row)

        layout.addWidget(tools_group)

        btn_box = QDialogButtonBox()
        btn_box.addButton(tr("Skip — I'll set up later"), QDialogButtonBox.RejectRole)
        done_btn = btn_box.addButton(tr("Continue"), QDialogButtonBox.AcceptRole)
        done_btn.setStyleSheet(
            "QPushButton { background-color: #198754; color: white; padding: 6px 20px; "
            "font-weight: bold; border-radius: 4px; }")
        layout.addWidget(btn_box)

        btn_box.rejected.connect(self.reject)
        btn_box.accepted.connect(self.accept)


class PreRunCheckDialog(QDialog):
    """Before each run: check which tools are needed and warn if missing.

    Offers: Copy install command(s) / Continue anyway (these will fail) / Cancel
    """

    def __init__(self, files: list[Path], parent=None):
        super().__init__(parent)
        self.files = files
        self._continue_anyway = False
        self.setWindowTitle(tr("mdmaker — Pre-Run Check"))
        self.setMinimumSize(520, 280)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel(
            tr(f"About to convert {len(self.files)} file(s).")))

        needed = tools_needed_for_files(self.files)
        missing_needed = [t for t in needed if not t.is_installed()]

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
            row.addWidget(QLabel(f"  ❌ {t.name} — {tr('needed for:')} {t.formats}"))
            if t.install_cmd:
                copy_btn = QPushButton(tr("📋 Copy"))
                copy_btn.setToolTip(t.install_cmd)
                copy_btn.clicked.connect(
                    lambda checked, c=t.install_cmd: QApplication.clipboard().setText(c))
                row.addWidget(copy_btn)
            layout.addLayout(row)

        layout.addWidget(QLabel(
            tr("Files that need missing tools will FAIL. "
               "Copy the install commands to fix, or continue anyway.")))

        btn_box = QDialogButtonBox()
        cancel_btn = btn_box.addButton(tr("Cancel"), QDialogButtonBox.RejectRole)
        continue_btn = btn_box.addButton(
            tr("Continue anyway (some will fail)"), QDialogButtonBox.AcceptRole)
        continue_btn.setStyleSheet("color: #dc3545;")
        layout.addWidget(btn_box)

        cancel_btn.clicked.connect(self.reject)
        continue_btn.clicked.connect(self._continue)

    def _continue(self):
        self._continue_anyway = True
        self.accept()

    @property
    def continue_anyway(self) -> bool:
        return self._continue_anyway
