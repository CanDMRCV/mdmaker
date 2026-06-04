"""Main window — folder picker, progress, results. Thin over core library."""

import threading
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTextEdit,
    QFileDialog, QGroupBox, QCheckBox, QSpinBox, QLineEdit,
    QListWidget, QListWidgetItem, QSplitter, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont, QColor

from ..pipeline import collect_files, convert_batch, check_all_dependencies
from ..detector import detect_format


class _WorkerSignals(QObject):
    """Signals for the worker thread (Naht Backend↔Frontend)."""
    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal(dict)            # summary dict
    failed_file = Signal(str, str)     # filename, reason


class ConvertWorker(QThread):
    """Runs convert_batch in a background thread. UI never blocks."""

    def __init__(self, paths: list[Path], output_dir: Path, *,
                 recursive: bool = True, jobs: int = 1, force: bool = False):
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
        def on_progress(current: int, total: int, filename: str):
            self.signals.progress.emit(current, total, filename)

        result = convert_batch(
            self.paths, self.output_dir,
            recursive=self.recursive,
            jobs=self.jobs,
            force=self.force,
            progress_callback=on_progress,
            cancel_event=self._cancel,
        )
        self.signals.finished.emit(result)


class MainWindow(QMainWindow):
    """mdmaker GUI — dünn über dem Kern (ADR: gleiche convert()-Bibliothek)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("mdmaker — E-Book → Markdown")
        self.setMinimumSize(800, 600)
        self._worker: ConvertWorker | None = None
        self._failed_files: list[tuple[str, str]] = []

        self._build_ui()
        self._refresh_deps()

    # ── UI Construction ──

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # ── DRM / Legal Notice (Design-Ethik-Gate) ──
        notice = QLabel(
            "Dieses Tool verarbeitet NUR Dateien, die Sie legal besitzen und öffnen dürfen. "
            "Keine DRM-Entfernung. Alle Verarbeitung erfolgt lokal auf Ihrem Rechner."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "background-color: #fff3cd; color: #664d03; padding: 8px; "
            "border: 1px solid #ffc107; border-radius: 4px; font-size: 11pt;"
        )
        layout.addWidget(notice)

        # ── Input / Output ──
        io_group = QGroupBox("Ein-/Ausgabe")
        io_layout = QVBoxLayout(io_group)

        # Input row
        in_row = QHBoxLayout()
        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText("Ordner mit E-Books auswählen...")
        in_row.addWidget(QLabel("Eingabe:"))
        in_row.addWidget(self._input_edit)
        btn_in = QPushButton("Durchsuchen...")
        btn_in.clicked.connect(self._pick_input)
        in_row.addWidget(btn_in)
        io_layout.addLayout(in_row)

        # Output row
        out_row = QHBoxLayout()
        self._output_edit = QLineEdit()
        self._output_edit.setPlaceholderText("_md_output")
        out_row.addWidget(QLabel("Ausgabe:"))
        out_row.addWidget(self._output_edit)
        btn_out = QPushButton("Durchsuchen...")
        btn_out.clicked.connect(self._pick_output)
        out_row.addWidget(btn_out)
        io_layout.addLayout(out_row)

        # Options row
        opt_row = QHBoxLayout()
        self._recursive_cb = QCheckBox("Rekursiv")
        self._recursive_cb.setChecked(True)
        opt_row.addWidget(self._recursive_cb)
        self._force_cb = QCheckBox("Überschreiben")
        opt_row.addWidget(self._force_cb)
        opt_row.addWidget(QLabel("Parallele Jobs:"))
        self._jobs_spin = QSpinBox()
        self._jobs_spin.setRange(1, 16)
        self._jobs_spin.setValue(4)
        opt_row.addWidget(self._jobs_spin)
        opt_row.addStretch()
        io_layout.addLayout(opt_row)
        layout.addWidget(io_group)

        # ── Dependency Status ──
        self._dep_status = QLabel("Prüfe Abhängigkeiten...")
        self._dep_status.setStyleSheet("padding: 4px; font-size: 10pt;")
        layout.addWidget(self._dep_status)

        # ── Progress ──
        prog_group = QGroupBox("Fortschritt")
        prog_layout = QVBoxLayout(prog_group)
        self._progress_bar = QProgressBar()
        prog_layout.addWidget(self._progress_bar)
        self._progress_label = QLabel("Bereit.")
        prog_layout.addWidget(self._progress_label)
        layout.addWidget(prog_group)

        # ── Results ──
        self._results_list = QListWidget()
        self._results_list.setAlternatingRowColors(True)
        layout.addWidget(QLabel("Ergebnisse:"))
        layout.addWidget(self._results_list)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("▶ Start")
        self._start_btn.setStyleSheet(
            "QPushButton { background-color: #198754; color: white; padding: 8px 24px; "
            "font-size: 13pt; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #157347; }"
            "QPushButton:disabled { background-color: #6c757d; }"
        )
        self._start_btn.clicked.connect(self._start_conversion)
        btn_row.addWidget(self._start_btn)

        self._cancel_btn = QPushButton("■ Abbrechen")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_conversion)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ── Status bar ──
        self.statusBar().showMessage("mdmaker — Bereit.")

    # ── Actions ──

    def _pick_input(self):
        d = QFileDialog.getExistingDirectory(self, "Eingabeordner wählen")
        if d:
            self._input_edit.setText(d)
            self._scan_files(Path(d))

    def _pick_output(self):
        d = QFileDialog.getExistingDirectory(self, "Ausgabeordner wählen")
        if d:
            self._output_edit.setText(d)

    def _scan_files(self, directory: Path):
        """Pre-scan: count supported files so user sees what will be processed."""
        try:
            files = collect_files([directory], recursive=self._recursive_cb.isChecked())
            self._progress_label.setText(f"{len(files)} unterstützte Dateien gefunden.")
        except Exception:
            pass

    def _refresh_deps(self):
        """Show --check status in the UI (Ethik-Gate: tools visible)."""
        issues = check_all_dependencies()
        if not issues:
            self._dep_status.setText("✅ Alle externen Tools verfügbar.")
            self._dep_status.setStyleSheet("color: #198754; padding: 4px; font-size: 10pt;")
        else:
            missing = ", ".join(issues.keys())
            self._dep_status.setText(f"⚠️ Fehlende Tools: {missing}")
            self._dep_status.setStyleSheet("color: #dc3545; padding: 4px; font-size: 10pt;")

    def _start_conversion(self):
        inp = self._input_edit.text().strip()
        outp = self._output_edit.text().strip() or "_md_output"

        if not inp:
            QMessageBox.warning(self, "Fehler", "Bitte Eingabeordner wählen.")
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
        self._worker.signals.finished.connect(self._on_finished)
        self._worker.signals.failed_file.connect(self._on_failed_file)

        self._results_list.clear()
        self._failed_files.clear()
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)
        self._progress_label.setText("Starte...")
        self.statusBar().showMessage("Konvertierung läuft...")

        self._worker.start()

    def _cancel_conversion(self):
        if self._worker:
            self._worker.cancel()
            self._progress_label.setText("Breche ab...")
            self._cancel_btn.setEnabled(False)

    def _on_progress(self, current: int, total: int, filename: str):
        if total > 0:
            pct = int(current / total * 100)
            self._progress_bar.setValue(pct)
        self._progress_label.setText(f"[{current}/{total}] {filename}")

    def _on_failed_file(self, filename: str, reason: str):
        self._failed_files.append((filename, reason))

    def _on_finished(self, summary: dict):
        self._progress_bar.setValue(100)
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._worker = None

        # Show summary
        total = summary["total"]
        ok = summary["ok"]
        skipped = summary["skipped"]
        failed = summary["failed"]
        elapsed = summary["elapsed_s"]

        self._progress_label.setText(
            f"Fertig: {ok} OK, {skipped} übersprungen, {failed} fehlgeschlagen — {elapsed:.1f}s"
        )
        self.statusBar().showMessage(
            f"OK: {ok} | SKIP: {skipped} | FAIL: {failed} | {elapsed:.1f}s"
        )

        # Ethisches Gate: Fehler SICHTBAR machen
        if failed > 0:
            item = QListWidgetItem(f"⚠️ {failed} Datei(en) fehlgeschlagen:")
            item.setForeground(QColor("#dc3545"))
            self._results_list.addItem(item)
            for fname, reason in self._failed_files:
                self._results_list.addItem(f"    {fname} — {reason}")
        else:
            item = QListWidgetItem(f"✅ Alle {ok} Dateien erfolgreich konvertiert.")
            item.setForeground(QColor("#198754"))
            self._results_list.addItem(item)
