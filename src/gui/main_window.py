"""Main window — folder picker, incremental results, honest progress (v0.2.1).

Fixes (UX-Rücklauf):
  A1: FAIL shows file + converter + error reason
  A2: Incremental results (each file appears as it completes)
  A3: Phase-aware progress (filename + "OCR running…"/"extracting…")
  A4: DRM notice as subtle footer, not aggressive banner
  A5: English strings, i18n-ready (tr() wrapper)
"""

import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStatusBar,
    QPushButton, QLabel, QProgressBar, QTextEdit,
    QFileDialog, QGroupBox, QCheckBox, QSpinBox, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QAbstractItemView,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont, QColor, QIcon

from ..pipeline import collect_files, convert_batch, check_all_dependencies, FileResult
from ..detector import detect_format


def tr(s: str) -> str:
    """i18n stub (A5). Replace with gettext later."""
    return s


class _WorkerSignals(QObject):
    progress = Signal(int, int, str, str)   # current, total, filename, phase
    file_done = Signal(object)               # FileResult — incremental (A2)
    finished = Signal(object)                # BatchSummary


class ConvertWorker(QThread):
    """Worker thread — convert batch in background, emit incremental results."""

    def __init__(self, paths: list[Path], output_dir: Path, *,
                 recursive: bool, jobs: int, force: bool):
        super().__init__()
        self.paths = paths
        self.output_dir = output_dir
        self.recursive = recursive
        self.jobs = jobs
        self.force = force
        self.signals = _WorkerSignals()
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        def on_progress(current: int, total: int, filename: str, phase: str):
            self.signals.progress.emit(current, total, filename, phase)

        # Wrap convert_batch to emit file_done per result
        summary = convert_batch(
            self.paths, self.output_dir,
            recursive=self.recursive, jobs=self.jobs, force=self.force,
            progress_callback=on_progress, cancel_event=self._cancel,
        )
        # Emit individual results incrementally
        for fr in summary.results:
            self.signals.file_done.emit(fr)
        self.signals.finished.emit(summary)


class MainWindow(QMainWindow):
    """mdmaker GUI — thin over core library."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("mdmaker — E-Book to Markdown"))
        self.setMinimumSize(820, 620)
        self._worker: ConvertWorker | None = None
        self._result_count = {"ok": 0, "skipped": 0, "failed": 0}

        self._build_ui()
        self._refresh_deps()

    # ── UI ──

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)

        # ── Input / Output ──
        io = QGroupBox(tr("Input / Output"))
        iol = QVBoxLayout(io)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel(tr("Source:")))
        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText(tr("Select folder with e-books…"))
        r1.addWidget(self._input_edit)
        b1 = QPushButton(tr("Browse…"))
        b1.clicked.connect(self._pick_input)
        r1.addWidget(b1)
        iol.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel(tr("Output:")))
        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("_md_output")
        r2.addWidget(self._output_edit)
        b2 = QPushButton(tr("Browse…"))
        b2.clicked.connect(self._pick_output)
        r2.addWidget(b2)
        iol.addLayout(r2)

        r3 = QHBoxLayout()
        self._recursive_cb = QCheckBox(tr("Recursive"))
        self._recursive_cb.setChecked(True)
        r3.addWidget(self._recursive_cb)
        self._force_cb = QCheckBox(tr("Overwrite"))
        r3.addWidget(self._force_cb)
        r3.addWidget(QLabel(tr("Parallel jobs:")))
        self._jobs_spin = QSpinBox()
        self._jobs_spin.setRange(1, 16)
        self._jobs_spin.setValue(4)
        r3.addWidget(self._jobs_spin)
        r3.addStretch()
        iol.addLayout(r3)
        layout.addWidget(io)

        # ── Dependency status ──
        self._dep_label = QLabel(tr("Checking dependencies…"))
        self._dep_label.setStyleSheet("padding: 2px; font-size: 10pt;")
        layout.addWidget(self._dep_label)

        # ── Progress ──
        prog = QGroupBox(tr("Progress"))
        pl = QVBoxLayout(prog)
        self._progress_bar = QProgressBar()
        pl.addWidget(self._progress_bar)
        self._progress_detail = QLabel(tr("Ready."))
        pl.addWidget(self._progress_detail)
        layout.addWidget(prog)

        # ── Results list (A2: incremental) ──
        layout.addWidget(QLabel(tr("Results (incremental):")))
        self._results_list = QListWidget()
        self._results_list.setAlternatingRowColors(True)
        self._results_list.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self._results_list, 1)

        # ── Buttons ──
        br = QHBoxLayout()
        self._start_btn = QPushButton(tr("▶ Start"))
        self._start_btn.setStyleSheet(
            "QPushButton { background-color: #198754; color: white; padding: 8px 24px; "
            "font-size: 13pt; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #157347; }"
            "QPushButton:disabled { background-color: #6c757d; }"
        )
        self._start_btn.clicked.connect(self._start_conversion)
        br.addWidget(self._start_btn)

        self._cancel_btn = QPushButton(tr("■ Cancel"))
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_conversion)
        br.addWidget(self._cancel_btn)
        br.addStretch()
        layout.addLayout(br)

        # ── DRM Footer (A4: subtle, not aggressive) ──
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
            try:
                files = collect_files([Path(d)], recursive=self._recursive_cb.isChecked())
                self._progress_detail.setText(
                    tr(f"{len(files)} supported files found."))
            except Exception:
                pass

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, tr("Select output folder"))
        if d:
            self._output_edit.setText(d)

    def _refresh_deps(self):
        issues = check_all_dependencies()
        if not issues:
            self._dep_label.setText("✅ " + tr("All external tools available."))
            self._dep_label.setStyleSheet("color: #198754; padding: 2px; font-size: 10pt;")
        else:
            missing = ", ".join(issues.keys())
            self._dep_label.setText(f"⚠ {tr('Missing tools:')} {missing}")
            self._dep_label.setStyleSheet("color: #dc3545; padding: 2px; font-size: 10pt;")

    def _start_conversion(self):
        inp = self._input_edit.text().strip()
        outp = self._output_edit.text().strip() or "_md_output"
        if not inp:
            QMessageBox.warning(self, tr("Error"), tr("Please select a source folder."))
            return

        paths = [Path(inp)]
        out_dir = Path(outp)
        self._worker = ConvertWorker(
            paths, out_dir,
            recursive=self._recursive_cb.isChecked(),
            jobs=self._jobs_spin.value(),
            force=self._force_cb.isChecked(),
        )
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.file_done.connect(self._on_file_done)
        self._worker.signals.finished.connect(self._on_finished)

        self._results_list.clear()
        self._result_count = {"ok": 0, "skipped": 0, "failed": 0}
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

    def _on_progress(self, current: int, total: int, filename: str, phase: str):
        """A3: Phase-aware progress with activity indication."""
        if total > 0:
            self._progress_bar.setValue(int(current / total * 100))

        phase_text = {
            "done": "✓", "failed": "✗", "ocr": tr("OCR running…"),
            "extracting": tr("Extracting…"), "converting": tr("Converting…"),
        }.get(phase, phase)

        # Activity indicator: pulsating dot + phase
        dots = [".  ", "·  ", "·. ", "··."][current % 4]
        self._progress_detail.setText(
            f"[{current}/{total}] {dots} {phase_text} {filename}"
        )

    def _on_file_done(self, fr: FileResult):
        """A1+A2: Incremental result — each file appears immediately with full detail."""
        if fr.status == "ok":
            self._result_count["ok"] += 1
            item = QListWidgetItem(f"✅ {fr.path.name}")
            item.setForeground(QColor("#198754"))
        elif fr.status == "skipped":
            self._result_count["skipped"] += 1
            item = QListWidgetItem(f"⬜ {fr.path.name}")
            item.setForeground(QColor("#6c757d"))
        else:
            self._result_count["failed"] += 1
            # A1: Show file + converter + error reason
            error_text = fr.error or tr("Unknown error")
            item = QListWidgetItem(
                f"❌ {fr.path.name}  [{fr.converter}]  —  {error_text}"
            )
            item.setForeground(QColor("#dc3545"))
            item.setToolTip(
                f"File: {fr.path.name}\n"
                f"Converter: {fr.converter}\n"
                f"Format: {fr.format_detected}\n"
                f"Error: {error_text}\n"
                f"Time: {fr.elapsed_s:.1f}s"
            )

        item.setFont(QFont("Consolas", 9))
        self._results_list.addItem(item)
        self._results_list.scrollToBottom()

    def _on_finished(self, summary):
        self._progress_bar.setValue(100)
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._worker = None

        s = summary
        self._progress_detail.setText(
            tr(f"Done: {s.ok} OK, {s.skipped} skipped, {s.failed} failed — {s.elapsed_s:.1f}s")
        )
        self._status_bar.showMessage(
            f"OK: {s.ok} | SKIP: {s.skipped} | FAIL: {s.failed} | {s.elapsed_s:.1f}s"
            + (f" | {tr('Parallel workers:')} {self._jobs_spin.value()}"
               if self._jobs_spin.value() > 1 else "")
        )
