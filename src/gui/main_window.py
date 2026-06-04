"""Main window — v0.2.2 (Rücklauf 2: copyable, preventive check, better errors).

Studio-Regel (Design v1.1.0): All status/error text MUST be selectable & copyable.
"""

import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStatusBar,
    QPushButton, QLabel, QProgressBar, QTextEdit, QTextBrowser,
    QFileDialog, QGroupBox, QCheckBox, QSpinBox, QLineEdit,
    QMessageBox, QSplitter, QApplication,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont, QColor

from ..pipeline import collect_files, convert_batch, check_all_dependencies, FileResult
from ..detector import detect_format, classify_pdf


def tr(s: str) -> str:
    return s  # i18n stub (A5)


def _ocr_needed(path: Path) -> bool:
    """Quick pre-scan: does this file likely need OCR?"""
    if path.suffix.lower() != ".pdf":
        return False
    return classify_pdf(path) == "pdf_scan"


def _tool_for_format(fmt: str) -> str:
    """Map format to required external tool (B3)."""
    return {
        "pdf_scan": "Tesseract OCR",
        "epub": "Calibre", "mobi": "Calibre", "prc": "Calibre",
        "doc": "Word or LibreOffice",
        "djvu": "DjVuLibre",
        "chm": "7-Zip",
    }.get(fmt, "")


def _remedy_for(format_needs: str) -> str:
    """User-friendly remedy hint (B5)."""
    remedies = {
        "Tesseract OCR": "Install: winget install tesseract-ocr.tesseract",
        "Calibre": "Install: winget install calibre",
        "DjVuLibre": "Install: winget install DjVuLibre.DjView",
        "7-Zip": "Install: winget install 7zip.7zip",
        "Word or LibreOffice": "Install Word (Windows) or LibreOffice",
    }
    return remedies.get(format_needs, "")


class _WorkerSignals(QObject):
    progress = Signal(int, int, str, str)
    file_done = Signal(object)
    finished = Signal(object)


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
        self.setMinimumSize(860, 660)
        self._worker: ConvertWorker | None = None
        self._result_text = ""  # Accumulate for copy

        self._build_ui()
        self._refresh_deps()

    # ── UI ──

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(6)

        # ── Input / Output ──
        io = QGroupBox(tr("Input / Output"))
        iol = QVBoxLayout(io)
        for label_text, attr, placeholder in [
            ("Source:", "_input_edit", "Select folder with e-books…"),
            ("Output:", "_output_edit", "_md_output"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(tr(label_text)))
            edit = QLineEdit()
            edit.setPlaceholderText(tr(placeholder))
            row.addWidget(edit)
            btn = QPushButton(tr("Browse…"))
            btn.clicked.connect(
                self._pick_input if "Source" in label_text else self._pick_output
            )
            row.addWidget(btn)
            iol.addLayout(row)
            setattr(self, attr, edit)

        opt_row = QHBoxLayout()
        self._recursive_cb = QCheckBox(tr("Recursive"))
        self._recursive_cb.setChecked(True)
        opt_row.addWidget(self._recursive_cb)
        self._force_cb = QCheckBox(tr("Overwrite"))
        opt_row.addWidget(self._force_cb)
        opt_row.addWidget(QLabel(tr("Parallel jobs:")))
        self._jobs_spin = QSpinBox(); self._jobs_spin.setRange(1, 16); self._jobs_spin.setValue(4)
        opt_row.addWidget(self._jobs_spin)
        opt_row.addStretch()
        iol.addLayout(opt_row)
        layout.addWidget(io)

        # ── Dependency + Pre-scan warning area ──
        self._dep_label = QLabel(tr("Checking dependencies…"))
        self._dep_label.setStyleSheet("padding: 2px; font-size: 10pt;")
        layout.addWidget(self._dep_label)

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

        # ── Results: QTextBrowser (SELECTABLE + COPYABLE — A1, Studio-Regel) ──
        layout.addWidget(QLabel(tr("Results (selectable & copyable):")))
        self._results_view = QTextBrowser()
        self._results_view.setFont(QFont("Consolas", 9))
        self._results_view.setOpenExternalLinks(False)
        self._results_view.setReadOnly(True)
        layout.addWidget(self._results_view, 1)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton(tr("▶ Start"))
        self._start_btn.setStyleSheet(
            "QPushButton { background-color: #198754; color: white; padding: 8px 24px; "
            "font-size: 13pt; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #157347; }"
            "QPushButton:disabled { background-color: #6c757d; }"
        )
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
            tr("Processes only files you legally own. No DRM removal. All processing local.")
        )
        self.setStatusBar(self._status_bar)

    # ── Actions ──

    def _pick_input(self):
        d = QFileDialog.getExistingDirectory(self, tr("Select source folder"))
        if d:
            self._input_edit.setText(d)
            self._pre_scan(Path(d))

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, tr("Select output folder"))
        if d:
            self._output_edit.setText(d)

    def _pre_scan(self, directory: Path):
        """A2: Preventive OCR check BEFORE run. Warn if Tesseract missing."""
        files = collect_files([directory], recursive=self._recursive_cb.isChecked())
        ocr_needed = [f for f in files if _ocr_needed(f)]

        self._progress_detail.setText(tr(f"{len(files)} supported files, "
                                          f"{len(ocr_needed)} need OCR."))

        if ocr_needed:
            # Check if Tesseract is available
            ocr_deps = False
            for conv in __import__('src.converters', fromlist=['REGISTRY']).REGISTRY:
                if "OCR" in conv.label:
                    ocr_deps = len(conv.check_deps()) == 0
                    break

            if not ocr_deps:
                self._pre_scan_warning.setText(
                    tr(f"⚠ WARNING: {len(ocr_needed)} file(s) require OCR but "
                       f"Tesseract is not installed or not on PATH. "
                       f"These files will FAIL. Install Tesseract or convert them elsewhere.")
                )
                self._pre_scan_warning.show()
            else:
                self._pre_scan_warning.setText(
                    tr(f"ℹ {len(ocr_needed)} file(s) will use OCR (may be slower)."))
                self._pre_scan_warning.show()
        else:
            self._pre_scan_warning.hide()

    def _refresh_deps(self):
        """B3: Show missing tools + WHICH formats are blocked."""
        issues = check_all_dependencies()
        if not issues:
            self._dep_label.setText("✅ " + tr("All external tools available."))
            self._dep_label.setStyleSheet("color: #198754; padding: 2px; font-size: 10pt;")
        else:
            lines = []
            for label, msgs in issues.items():
                # Map converter label → affected formats
                affected = {
                    "EPUB/MOBI/PRC (Calibre)": "EPUB, MOBI, PRC",
                    "PDF scan -> OCR": "PDF (scanned)",
                    "DOC (Word COM / LibreOffice)": "DOC",
                    "DJVU (DjVuLibre)": "DJVU",
                }.get(label, label)
                lines.append(f"  • {affected}: {msgs[0].split(chr(10))[0]}")
            self._dep_label.setText("⚠ " + tr("Missing tools — these formats will FAIL:\n") + "\n".join(lines))
            self._dep_label.setStyleSheet("color: #dc3545; padding: 2px; font-size: 10pt;")

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

        self._results_view.clear()
        self._result_text = ""
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._status_bar.showMessage(tr("Converting…"))
        self._worker.start()

    def _cancel_conversion(self):
        if self._worker:
            self._worker.cancel()
            self._progress_detail.setText(tr("Cancelling…"))
            self._cancel_btn.setEnabled(False)

    # ── Signal handlers ──

    def _on_progress(self, current, total, filename, phase):
        if total > 0:
            self._progress_bar.setValue(int(current / total * 100))
        phase_text = {"done": "✓", "failed": "✗", "ocr": tr("OCR running…"),
                      "extracting": tr("Extracting…"), "converting": tr("Converting…")}.get(phase, phase)
        dots = [".  ", "·  ", "·. ", "··."][current % 4]
        self._progress_detail.setText(f"[{current}/{total}] {dots} {phase_text} {filename}")

    def _on_file_done(self, fr: FileResult):
        """A1+A2: Append selectable, copyable result line."""
        if fr.status == "ok":
            icon, color = "✅", "#198754"
            line = f"OK  {fr.path.name}  ({fr.elapsed_s:.1f}s)"
        elif fr.status == "skipped":
            icon, color = "⬜", "#6c757d"
            line = f"SKIP  {fr.path.name}"
        else:
            icon, color = "❌", "#dc3545"
            # B5: Clean error with remedy
            remedy = _remedy_for(_tool_for_format(fr.format_detected))
            hint = f" — Fix: {remedy}" if remedy else ""
            line = (f"FAIL  {fr.path.name}\n"
                    f"      Converter: {fr.converter}\n"
                    f"      Reason: {fr.error}{hint}")

        self._result_text += line + "\n"
        self._results_view.setHtml(
            f"<pre style='font-family:Consolas; font-size:9pt; color:{color}; "
            f"white-space:pre-wrap;'>{self._result_text}</pre>"
        )
        # Auto-scroll
        self._results_view.verticalScrollBar().setValue(
            self._results_view.verticalScrollBar().maximum()
        )

    def _on_finished(self, summary):
        self._progress_bar.setValue(100)
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._worker = None

        s = summary
        # Append summary to results
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
            f"{self._result_text}</pre>"
        )
        self._progress_detail.setText(
            tr(f"Done: {s.ok} OK, {s.skipped} skipped, {s.failed} failed — {s.elapsed_s:.1f}s"))
        self._status_bar.showMessage(
            f"OK: {s.ok} | SKIP: {s.skipped} | FAIL: {s.failed} | {s.elapsed_s:.1f}s")

    def _copy_results(self):
        """Copy all results to clipboard."""
        QApplication.clipboard().setText(self._result_text)
        self._status_bar.showMessage(tr("Results copied to clipboard."), 3000)
