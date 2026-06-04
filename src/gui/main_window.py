"""Main window — v0.3.0 (Rücklauf 3: perf, scan-in-worker, actionable setup).

Studio-Regeln (design v1.2.0):
  - "Offer solution, not just problem": actionable fix buttons
  - Copy-affordanz: all text selectable
"""

import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStatusBar,
    QPushButton, QLabel, QProgressBar, QTextBrowser,
    QFileDialog, QGroupBox, QCheckBox, QSpinBox, QLineEdit,
    QMessageBox, QDialog, QDialogButtonBox, QApplication,
    QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont, QColor

from ..pipeline import collect_files, convert_batch, check_all_dependencies, FileResult
from ..detector import classify_pdf


def tr(s: str) -> str:
    return s


def _ocr_needed(path: Path) -> bool:
    if path.suffix.lower() != ".pdf":
        return False
    try:
        return classify_pdf(path) == "pdf_scan"
    except Exception:
        return False


# ── Tool info (B3: which formats blocked + winget commands) ──

TOOL_INFO = {
    "Tesseract OCR": {
        "formats": "PDF (scanned)",
        "check": lambda: not any(Path(p).exists() for p in [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]) and __import__('shutil').which('tesseract') is None,
        "install": "winget install tesseract-ocr.tesseract",
    },
    "Calibre": {
        "formats": "EPUB, MOBI, PRC",
        "check": lambda: __import__('shutil').which('ebook-convert') is None,
        "install": "winget install calibre",
    },
    "DjVuLibre": {
        "formats": "DJVU",
        "check": lambda: __import__('shutil').which('djvutxt') is None and not Path(
            r"C:\Program Files (x86)\DjVuLibre\djvutxt.exe").exists(),
        "install": "winget install DjVuLibre.DjView",
    },
    "7-Zip": {
        "formats": "CHM",
        "check": lambda: __import__('shutil').which('7z') is None and __import__('shutil').which('7zz') is None,
        "install": "winget install 7zip.7zip",
    },
    "Word or LibreOffice": {
        "formats": "DOC",
        "check": lambda: __import__('shutil').which('winword') is None and __import__('shutil').which('libreoffice') is None,
        "install": "Install Microsoft Word or LibreOffice",
    },
}


class _WorkerSignals(QObject):
    progress = Signal(int, int, str, str)
    file_done = Signal(object)
    finished = Signal(object)
    scan_done = Signal(list, int)  # files list, ocr_count


class _ScanWorker(QThread):
    """A2: Scan input folder in background — UI never freezes."""

    def __init__(self, directory: Path, recursive: bool):
        super().__init__()
        self.directory = directory
        self.recursive = recursive
        self.signals = _WorkerSignals()

    def run(self):
        files = collect_files([self.directory], recursive=self.recursive)
        ocr_count = sum(1 for f in files if _ocr_needed(f))
        self.signals.scan_done.emit(files, ocr_count)


class ConvertWorker(QThread):
    def __init__(self, paths, output_dir, *, recursive, jobs, force):
        super().__init__()
        self.paths = paths; self.output_dir = output_dir
        self.recursive = recursive; self.jobs = jobs; self.force = force
        self.signals = _WorkerSignals()
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        def cb(current, total, filename, phase):
            self.signals.progress.emit(current, total, filename, phase)
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
        self._build_ui()
        self._refresh_deps()

    # ── UI ──

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(6)

        # ── Tool status bar (B3 + A3: actionable) ──
        self._tool_frame = QFrame()
        self._tool_frame.setFrameStyle(QFrame.StyledPanel)
        self._tool_frame.setStyleSheet("QFrame { background: #f8f9fa; border-radius: 4px; padding: 4px; }")
        tool_layout = QVBoxLayout(self._tool_frame)
        tool_layout.setSpacing(2)
        self._tool_status_label = QLabel(tr("Checking tools…"))
        tool_layout.addWidget(self._tool_status_label)
        self._tool_buttons_layout = QHBoxLayout()
        tool_layout.addLayout(self._tool_buttons_layout)
        layout.addWidget(self._tool_frame)

        # ── Input / Output ──
        io = QGroupBox(tr("Input / Output"))
        iol = QVBoxLayout(io)
        for lbl, attr, placeholder in [
            ("Source:", "_input_edit", "Select folder with e-books…"),
            ("Output:", "_output_edit", "_md_output"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(tr(lbl)))
            edit = QLineEdit()
            edit.setPlaceholderText(tr(placeholder))
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

        # ── Pre-scan warning ──
        self._pre_scan_warning = QLabel("")
        self._pre_scan_warning.setWordWrap(True)
        self._pre_scan_warning.setStyleSheet(
            "background-color: #fff3cd; color: #664d03; padding: 4px; "
            "border: 1px solid #ffc107; border-radius: 3px; font-size: 10pt;"
        )
        self._pre_scan_warning.hide()
        layout.addWidget(self._pre_scan_warning)

        # ── Progress ──
        self._progress_bar = QProgressBar()
        layout.addWidget(self._progress_bar)
        self._progress_detail = QLabel(tr("Ready."))
        layout.addWidget(self._progress_detail)

        # ── Results ──
        self._results_view = QTextBrowser()
        self._results_view.setFont(QFont("Consolas", 9))
        self._results_view.setReadOnly(True)
        self._results_view.setOpenExternalLinks(False)
        layout.addWidget(self._results_view, 1)

        # ── Buttons ──
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
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── DRM Footer ──
        self._status_bar = QStatusBar()
        self._status_bar.showMessage(
            tr("Processes only files you legally own. No DRM removal. All processing local."))
        self.setStatusBar(self._status_bar)

    # ── Tool status + Actionable setup ──

    def _refresh_deps(self):
        """A3: Show missing tools with clickable Install buttons."""
        lines = []; buttons_exist = False
        # Clear old buttons
        while self._tool_buttons_layout.count():
            w = self._tool_buttons_layout.takeAt(0).widget()
            if w: w.deleteLater()

        all_ok = True
        for name, info in TOOL_INFO.items():
            if info["check"]():
                all_ok = False
                lines.append(f"  ❌ {name} — {info['formats']}")
                btn = QPushButton(tr(f"Install {name}"))
                cmd = info["install"]
                btn.setToolTip(cmd)
                btn.setStyleSheet("QPushButton { color: #dc3545; font-size: 9pt; }")
                btn.clicked.connect(lambda checked, c=cmd: self._copy_command(c))
                self._tool_buttons_layout.addWidget(btn)
                buttons_exist = True

        if all_ok:
            self._tool_status_label.setText("✅ " + tr("All external tools available."))
            self._tool_status_label.setStyleSheet("color: #198754;")
        else:
            self._tool_status_label.setText(
                "⚠ " + tr("Missing tools — click to copy install command:\n") + "\n".join(lines))
            self._tool_status_label.setStyleSheet("color: #dc3545; font-size: 9pt;")

        if not buttons_exist:
            self._tool_frame.hide()
        else:
            self._tool_frame.show()

    def _copy_command(self, cmd: str):
        QApplication.clipboard().setText(cmd)
        self._status_bar.showMessage(tr(f"Copied: {cmd}"), 5000)

    # ── Folder scanning ──

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
        """A2: Scan in worker thread — UI stays responsive."""
        self._progress_detail.setText(tr("Scanning folder…"))
        self._pre_scan_warning.hide()
        self._scan_worker = _ScanWorker(directory, self._recursive_cb.isChecked())
        self._scan_worker.signals.scan_done.connect(self._on_scan_done)
        self._scan_worker.start()

    def _on_scan_done(self, files: list, ocr_count: int):
        """Handle scan results + show OCR warning if needed."""
        self._progress_detail.setText(
            tr(f"{len(files)} supported files found, {ocr_count} need OCR."))

        if ocr_count > 0:
            tesseract_ok = not TOOL_INFO["Tesseract OCR"]["check"]()
            if not tesseract_ok:
                self._pre_scan_warning.setText(
                    tr(f"⚠ {ocr_count} file(s) need OCR but Tesseract is missing. "
                       f"They will FAIL. Click 'Install Tesseract OCR' above to fix."))
                self._pre_scan_warning.show()
            else:
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
            remedy = TOOL_INFO.get(
                {"pdf_scan": "Tesseract OCR", "epub": "Calibre", "mobi": "Calibre",
                 "djvu": "DjVuLibre", "chm": "7-Zip"}.get(fr.format_detected, ""), {}
            ).get("install", "")
            hint = f"\n      Fix: {remedy}" if remedy else ""
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
        self._worker = None
        s = summary

        summary_text = (
            f"\n{'='*50}\n"
            f"SUMMARY: {s.ok} OK, {s.skipped} skipped, {s.failed} failed — {s.elapsed_s:.1f}s\n"
            f"Parallel workers: {self._jobs_spin.value()}\n"
        )
        if s.converter_times:
            summary_text += "Time by converter:\n"
            for label, secs in sorted(s.converter_times.items(), key=lambda x: -x[1]):
                summary_text += f"  {label}: {secs:.1f}s\n"

        self._result_text += summary_text
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
