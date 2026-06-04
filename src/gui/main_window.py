"""Main window — v0.3.2 (Rücklauf 4: fixed tool detection, clean status, scan in worker).

Studio-Regeln (design v1.2.0):
  - Copy-affordanz: all text selectable + copyable buttons
  - "Offer solution, not just problem": actionable, CORRECT commands
"""

import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStatusBar,
    QPushButton, QLabel, QProgressBar, QTextBrowser,
    QFileDialog, QGroupBox, QCheckBox, QSpinBox, QLineEdit,
    QMessageBox, QApplication, QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer, QSettings
from PySide6.QtGui import QFont, QColor

from ..pipeline import collect_files, convert_batch, FileResult
from ..detector import classify_pdf
from .setup_dialog import SetupDialog, PreRunCheckDialog
from .tool_detection import (
    ALL_TOOLS, ToolInfo, missing_tools, tools_needed_for_files,
    tr as _tr,
)

tr = _tr


def _ocr_needed(path: Path) -> bool:
    if path.suffix.lower() != ".pdf":
        return False
    try:
        return classify_pdf(path) == "pdf_scan"
    except Exception:
        return False


class _Signals(QObject):
    progress = Signal(int, int, str, str)
    file_done = Signal(object)
    finished = Signal(object)
    scan_done = Signal(list, int)
    tools_checked = Signal()  # refresh tool bar after background check


class _ScanWorker(QThread):
    """Scan folder + check tools in background — UI never freezes (B6)."""

    def __init__(self, directory: Path, recursive: bool):
        super().__init__()
        self.directory = directory; self.recursive = recursive
        self.signals = _Signals()

    def run(self):
        files = collect_files([self.directory], recursive=self.recursive)
        ocr_count = sum(1 for f in files if _ocr_needed(f))
        self.signals.scan_done.emit(files, ocr_count)


class ConvertWorker(QThread):
    def __init__(self, paths, output_dir, *, recursive, jobs, force):
        super().__init__()
        self.paths = paths; self.output_dir = output_dir
        self.recursive = recursive; self.jobs = jobs; self.force = force
        self.signals = _Signals()
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        def cb(c, t, f, p):
            self.signals.progress.emit(c, t, f, p)
        summary = convert_batch(
            self.paths, self.output_dir,
            recursive=self.recursive, jobs=self.jobs, force=self.force,
            progress_callback=cb, cancel_event=self._cancel,
        )
        for fr in summary.results:
            self.signals.file_done.emit(fr)
        self.signals.finished.emit(summary)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("mdmaker — E-Book to Markdown"))
        self.setMinimumSize(880, 680)
        self._worker: ConvertWorker | None = None
        self._scan_worker: _ScanWorker | None = None
        self._result_text = ""
        self._scanned_files: list[Path] = []
        self._build_ui()
        QTimer.singleShot(100, self._refresh_tools)
        QTimer.singleShot(400, self._check_first_run)

    # ── UI ──

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(6)

        # ── Tool status (B4/B5: clean, one line per tool, copyable) ──
        self._tool_frame = QFrame()
        self._tool_frame.setFrameStyle(QFrame.StyledPanel)
        self._tool_frame.setStyleSheet(
            "QFrame { background: #f8f9fa; border-radius: 4px; padding: 4px; }")
        self._tool_layout = QVBoxLayout(self._tool_frame)
        self._tool_layout.setSpacing(1)
        self._tool_status_label = QLabel(tr("Checking tools…"))
        self._tool_layout.addWidget(self._tool_status_label)
        layout.addWidget(self._tool_frame)

        # ── I/O ──
        io = QGroupBox(tr("Input / Output"))
        iol = QVBoxLayout(io)
        for lbl, attr, ph in [
            ("Source:", "_input_edit", "Select folder with e-books…"),
            ("Output:", "_output_edit", "_md_output"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(tr(lbl)))
            edit = QLineEdit(); edit.setPlaceholderText(tr(ph))
            row.addWidget(edit)
            btn = QPushButton(tr("Browse…"))
            btn.clicked.connect(self._pick_input if "Source" in lbl else self._pick_output)
            row.addWidget(btn)
            iol.addLayout(row)
            setattr(self, attr, edit)

        opt_row = QHBoxLayout()
        self._recursive_cb = QCheckBox(tr("Recursive"))
        self._recursive_cb.setChecked(True); opt_row.addWidget(self._recursive_cb)
        self._force_cb = QCheckBox(tr("Overwrite")); opt_row.addWidget(self._force_cb)
        opt_row.addWidget(QLabel(tr("Parallel jobs:")))
        self._jobs_spin = QSpinBox(); self._jobs_spin.setRange(1, 16); self._jobs_spin.setValue(4)
        opt_row.addWidget(self._jobs_spin)
        opt_row.addStretch()
        iol.addLayout(opt_row)
        layout.addWidget(io)

        self._pre_scan_warning = QLabel("")
        self._pre_scan_warning.setWordWrap(True)
        self._pre_scan_warning.setStyleSheet(
            "background-color: #fff3cd; color: #664d03; padding: 4px; "
            "border: 1px solid #ffc107; border-radius: 3px; font-size: 10pt;")
        self._pre_scan_warning.hide()
        layout.addWidget(self._pre_scan_warning)

        self._progress_bar = QProgressBar()
        layout.addWidget(self._progress_bar)
        self._progress_detail = QLabel(tr("Ready."))
        layout.addWidget(self._progress_detail)

        self._results_view = QTextBrowser()
        self._results_view.setFont(QFont("Consolas", 9))
        self._results_view.setReadOnly(True)
        self._results_view.setOpenExternalLinks(False)
        layout.addWidget(self._results_view, 1)

        btn_row = QHBoxLayout()
        style = ("QPushButton { background-color: #198754; color: white; padding: 8px 24px; "
                 "font-size: 13pt; font-weight: bold; border-radius: 4px; }"
                 "QPushButton:hover { background-color: #157347; }"
                 "QPushButton:disabled { background-color: #6c757d; }")
        self._start_btn = QPushButton(tr("▶ Start"))
        self._start_btn.setStyleSheet(style)
        self._start_btn.clicked.connect(self._start_conversion)
        btn_row.addWidget(self._start_btn)
        self._cancel_btn = QPushButton(tr("■ Cancel"))
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_conversion)
        btn_row.addWidget(self._cancel_btn)
        self._copy_btn = QPushButton(tr("📋 Copy All"))
        self._copy_btn.clicked.connect(self._copy_results)
        btn_row.addWidget(self._copy_btn)
        self._setup_btn = QPushButton(tr("⚙ Setup"))
        self._setup_btn.clicked.connect(self._show_setup)
        btn_row.addWidget(self._setup_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._status_bar = QStatusBar()
        self._status_bar.showMessage(
            tr("Processes only files you legally own. No DRM removal. All processing local."))
        self.setStatusBar(self._status_bar)

    # ── Setup ──

    def _check_first_run(self):
        settings = QSettings("Eisenagel", "mdmaker")
        if not settings.value("setup/completed", False, type=bool):
            dlg = SetupDialog(self)
            dlg.exec()
            settings.setValue("setup/completed", True)
            self._refresh_tools()

    def _show_setup(self):
        dlg = SetupDialog(self)
        dlg.exec()
        self._refresh_tools()

    # ── B4/B5: Clean tool status — one line per missing tool, copyable command ──

    def _refresh_tools(self):
        # Clear old rows
        while self._tool_layout.count() > 1:
            w = self._tool_layout.takeAt(1)
            if w.widget(): w.widget().deleteLater()
            elif w.layout():
                while w.layout().count():
                    cw = w.layout().takeAt(0).widget()
                    if cw: cw.deleteLater()

        missing = [t for t in ALL_TOOLS.values() if not t.is_installed()]

        if not missing:
            self._tool_status_label.setText("✅ " + tr("All tools ready."))
            self._tool_status_label.setStyleSheet("color: #198754; padding: 2px;")
        else:
            self._tool_status_label.setText("⚠ " + tr("Missing tools:"))
            self._tool_status_label.setStyleSheet("color: #dc3545; padding: 2px; font-weight: bold;")

            for t in missing:
                row = QHBoxLayout()
                row.setSpacing(4)

                # Tool name + what it's for
                label = QLabel(f"  ❌ {t.name} — {tr('needed for:')} {t.formats}")
                label.setStyleSheet("color: #dc3545; font-size: 9pt;")
                row.addWidget(label, 1)

                # Install command (copyable!) or install note
                cmd = t.install_cmd
                if cmd:
                    copy_btn = QPushButton(tr("📋 Copy"))
                    copy_btn.setToolTip(cmd)
                    copy_btn.setStyleSheet(
                        "QPushButton { font-size: 8pt; padding: 2px 6px; }"
                        "QPushButton:hover { background: #e2e6ea; }")
                    copy_btn.clicked.connect(lambda checked, c=cmd: self._copy_to_clipboard(c))
                    row.addWidget(copy_btn)

                    if hasattr(self, '_tool_frame'):
                        install_cmd_text = cmd
                else:
                    # No winget command (Word) — show install note
                    note_label = QLabel(t.install_note[:80] if t.install_note else "")
                    note_label.setStyleSheet("color: #6c757d; font-size: 8pt;")
                    note_label.setWordWrap(True)
                    row.addWidget(note_label, 2)

                self._tool_layout.addLayout(row)

    def _copy_to_clipboard(self, text: str):
        QApplication.clipboard().setText(text)
        self._status_bar.showMessage(tr(f"Copied: {text}"), 4000)

    # ── Folder scanning (B6: in worker thread) ──

    def _pick_input(self):
        d = QFileDialog.getExistingDirectory(self, tr("Select source folder"))
        if d:
            self._input_edit.setText(d)
            self._start_scan(Path(d))

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, tr("Select output folder"))
        if d:
            self._output_edit.setText(d)

    def _start_scan(self, directory: Path):
        self._progress_detail.setText(tr("Scanning folder…"))
        self._pre_scan_warning.hide()
        self._scan_worker = _ScanWorker(directory, self._recursive_cb.isChecked())
        self._scan_worker.signals.scan_done.connect(self._on_scan_done)
        self._scan_worker.start()

    def _on_scan_done(self, files: list, ocr_count: int):
        self._scanned_files = files
        self._progress_detail.setText(
            tr(f"{len(files)} supported files found, {ocr_count} need OCR."))
        t = ALL_TOOLS.get("tesseract")
        if ocr_count > 0 and t and not t.is_installed():
            self._pre_scan_warning.setText(
                tr(f"⚠ {ocr_count} file(s) need OCR but Tesseract is missing. "
                   f"They will FAIL. Copy the install command above to fix."))
            self._pre_scan_warning.show()
        elif ocr_count > 0:
            self._pre_scan_warning.setText(
                tr(f"ℹ {ocr_count} file(s) will use OCR (may be slower)."))
            self._pre_scan_warning.show()
        else:
            self._pre_scan_warning.hide()

    # ── Conversion ──

    def _start_conversion(self):
        inp = self._input_edit.text().strip()
        outp = self._output_edit.text().strip() or "_md_output"
        if not inp:
            QMessageBox.warning(self, tr("Error"), tr("Please select a source folder."))
            return

        files = self._scanned_files if self._scanned_files else collect_files(
            [Path(inp)], recursive=self._recursive_cb.isChecked())

        # B6: PreRunCheck uses background scan results (no UI freeze)
        dlg = PreRunCheckDialog(files, self)
        if dlg.exec() == QMessageBox.Rejected:
            return

        self._worker = ConvertWorker(
            [Path(inp)], Path(outp),
            recursive=self._recursive_cb.isChecked(),
            jobs=self._jobs_spin.value(),
            force=self._force_cb.isChecked(),
        )
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.file_done.connect(self._on_file_done)
        self._worker.signals.finished.connect(self._on_finished)

        self._results_view.clear(); self._result_text = ""
        self._progress_bar.setMaximum(100); self._progress_bar.setValue(0)
        self._start_btn.setEnabled(False); self._cancel_btn.setEnabled(True)
        self._status_bar.showMessage(tr("Converting…"))
        self._worker.start()

    def _cancel_conversion(self):
        if self._worker:
            self._worker.cancel()
            self._progress_detail.setText(tr("Cancelling…"))
            self._cancel_btn.setEnabled(False)

    # ── Progress ──

    def _on_progress(self, current, total, filename, phase):
        if total > 0:
            self._progress_bar.setValue(int(current / total * 100))
        phase_text = {"done": "✓", "failed": "✗", "ocr": tr("OCR running…"),
                      "extracting": tr("Extracting…"), "converting": tr("Converting…")}.get(phase, phase)
        dots = [".  ", "·  ", "·. ", "··."][current % 4]
        self._progress_detail.setText(f"[{current}/{total}] {dots} {phase_text} {filename}")

    def _on_file_done(self, fr: FileResult):
        if fr.status == "ok":
            color, line = "#198754", f"OK  {fr.path.name}  ({fr.elapsed_s:.1f}s)"
        elif fr.status == "skipped":
            color, line = "#6c757d", f"SKIP  {fr.path.name}"
        else:
            color = "#dc3545"
            # Map format to tool for remedy hint
            fmts = {"pdf_scan": "tesseract", "epub": "calibre", "mobi": "calibre",
                    "djvu": "djvu", "chm": "7zip"}
            tool = ALL_TOOLS.get(fmts.get(fr.format_detected, ""))
            hint = ""
            if tool and tool.install_cmd:
                hint = f"\n      Fix: {tool.install_cmd}"
            elif tool and tool.install_note:
                hint = f"\n      Fix: {tool.install_note}"
            line = (f"FAIL  {fr.path.name}\n"
                    f"      Converter: {fr.converter}\n"
                    f"      Reason: {fr.error}{hint}")

        self._result_text += line + "\n"
        self._results_view.setHtml(
            f"<pre style='font-family:Consolas; font-size:9pt; color:{color}; "
            f"white-space:pre-wrap;'>{self._result_text}</pre>")
        self._results_view.verticalScrollBar().setValue(
            self._results_view.verticalScrollBar().maximum())

    def _on_finished(self, summary):
        self._progress_bar.setValue(100)
        self._start_btn.setEnabled(True); self._cancel_btn.setEnabled(False)
        self._worker = None; s = summary

        st = (f"\n{'='*50}\n"
              f"SUMMARY: {s.ok} OK, {s.skipped} skipped, {s.failed} failed — {s.elapsed_s:.1f}s\n"
              f"Parallel workers: {self._jobs_spin.value()}\n")
        if s.converter_times:
            st += "Time by converter:\n"
            for label, secs in sorted(s.converter_times.items(), key=lambda x: -x[1]):
                st += f"  {label}: {secs:.1f}s\n"

        self._result_text += st
        self._results_view.setHtml(
            f"<pre style='font-family:Consolas; font-size:9pt; white-space:pre-wrap;'>"
            f"{self._result_text}</pre>")
        self._progress_detail.setText(
            tr(f"Done: {s.ok} OK, {s.skipped} skipped, {s.failed} failed — {s.elapsed_s:.1f}s"))
        self._status_bar.showMessage(
            f"OK: {s.ok} | SKIP: {s.skipped} | FAIL: {s.failed} | {s.elapsed_s:.1f}s")

    def _copy_results(self):
        QApplication.clipboard().setText(self._result_text)
        self._status_bar.showMessage(tr("Results copied to clipboard."), 3000)
