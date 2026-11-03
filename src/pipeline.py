"""Pipeline orchestrator — detection → routing → conversion (ADR-001).

v0.5.1: CREATE_NO_WINDOW on all subprocess calls, per-file progress notifications,
        magic-byte detection, lazy converter imports, PyMuPDF fallback,
        pure-Python EPUB (no Calibre). Rich FileResult/BatchSummary for GUI.
"""

import sys
import os
import shutil
import tempfile
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

# Fix for PyInstaller windowed mode (console=False): sys.stdout/stderr are None.
# tqdm.write() and tqdm() itself crash on None streams. Redirect to devnull.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from tqdm import tqdm

from .detector import detect_format, classify_pdf, detect_by_magic
from .converters import find_converter, sanitize_filename, check_all_deps as _check_all_converter_deps


@dataclass
class FileResult:
    """Per-file conversion result (A1: Fehler-Transparenz)."""
    path: Path
    status: str          # "ok" | "skipped" | "failed"
    converter: str        # converter label
    format_detected: str  # e.g. "epub", "pdf_text", "pdf_scan"
    error: str            # empty if ok/skipped
    elapsed_s: float      # seconds for this file
    output_md: Optional[Path] = None


@dataclass
class BatchSummary:
    """Full result of a batch conversion."""
    total: int
    ok: int
    skipped: int
    failed: int
    elapsed_s: float
    results: list[FileResult] = field(default_factory=list)
    converter_times: dict[str, float] = field(default_factory=dict)


def check_all_dependencies() -> dict[str, list[str]]:
    return _check_all_converter_deps()


def collect_files(paths: list[Path], recursive: bool = False) -> list[Path]:
    SUPPORTED = {
        ".epub", ".mobi", ".azw", ".azw3", ".prc",
        ".pdf", ".doc", ".docx", ".djvu", ".chm", ".xz", ".zip", ".lit",
    }
    seen: set[str] = set()
    files: list[Path] = []
    for p in paths:
        if not p.exists():
            tqdm.write(f"[!] Skipping (not found): {p}")
            continue
        if p.is_file():
            if p.suffix.lower() in SUPPORTED:
                key = str(p.resolve())
                if key not in seen:
                    seen.add(key)
                    files.append(p)
            continue
        pattern = "**/*" if recursive else "*"
        for f in sorted(p.glob(pattern)):
            if f.is_file() and f.suffix.lower() in SUPPORTED:
                key = str(f.resolve())
                if key not in seen:
                    seen.add(key)
                    files.append(f)
    return files


def convert_file(path: Path, output_dir: Path,
                 force: bool = False, dry_run: bool = False) -> FileResult:
    """Convert one file. Returns structured FileResult."""
    t0 = time.perf_counter()
    md_path = output_dir / (sanitize_filename(path.stem) + ".md")

    # Skip BEFORE detection/classification — reruns over big folders stay instant.
    if md_path.exists() and not force:
        return FileResult(path=path, status="skipped", converter="—",
                          format_detected="—", error="",
                          elapsed_s=time.perf_counter() - t0, output_md=md_path)

    fmt = detect_format(path)
    conv_label = "unknown"
    error = ""

    if fmt == "unknown":
        try:
            size = path.stat().st_size
        except Exception:
            size = 0
        if size < 100:
            error = f"Skipping tiny file ({size} bytes)"
        else:
            magic_type = detect_by_magic(path)
            if magic_type == "html":
                error = "Not a book file (HTML detected)"
            else:
                error = f"Unknown format (magic: {magic_type or 'none'}, ext: {path.suffix})"
        return FileResult(path=path, status="failed", converter="—",
                          format_detected="unknown", error=error,
                          elapsed_s=time.perf_counter() - t0)

    if fmt == "pdf_text":
        fmt = classify_pdf(path)

    converter = find_converter(fmt)
    if converter is None:
        return FileResult(path=path, status="failed", converter="—",
                          format_detected=fmt, error=f"No converter for '{fmt}'",
                          elapsed_s=time.perf_counter() - t0)

    conv_label = converter.label

    if dry_run:
        tqdm.write(f"   [*] Would convert [{conv_label}]: {path.name}")
        return FileResult(path=path, status="skipped", converter=conv_label,
                          format_detected=fmt, error="",
                          elapsed_s=time.perf_counter() - t0, output_md=md_path)

    # Convert into a private temp dir, then os.replace() into place: a crash,
    # Ctrl+C or cancel never leaves a half-written .md that the next run would
    # "skip" as done. Also keeps converter scratch files (.txt) out of output_dir.
    # ponytail: a hard kill can leave an empty .mdmaker_* dir behind — harmless.
    tmp_dir = Path(tempfile.mkdtemp(prefix=".mdmaker_", dir=output_dir))
    try:
        result = converter.convert(path, tmp_dir)
        ok = result is not None and result.exists() and result.stat().st_size > 100
        final = None
        if ok:
            final = output_dir / result.name
            os.replace(result, final)
        return FileResult(path=path,
                          status="ok" if ok else "failed",
                          converter=conv_label, format_detected=fmt,
                          error="" if ok else "Output too small or missing",
                          elapsed_s=time.perf_counter() - t0,
                          output_md=final)
    except Exception as e:
        return FileResult(path=path, status="failed", converter=conv_label,
                          format_detected=fmt, error=f"{type(e).__name__}: {e}",
                          elapsed_s=time.perf_counter() - t0)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def convert_batch(
    paths: list[Path],
    output_dir: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    recursive: bool = False,
    jobs: int = 1,
    progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> BatchSummary:
    """Convert a batch of files with progress reporting.

    progress_callback receives (current, total, filename, phase) where:
      - current: files completed so far (or being processed)
      - total: total files
      - filename: name of file being processed
      - phase: "converting" | "done" | "failed"

    Files that already have output (skipped) are reported as "done" immediately.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    files = collect_files(paths, recursive=recursive)

    if not files:
        tqdm.write("No supported files found.")
        return BatchSummary(total=0, ok=0, skipped=0, failed=0, elapsed_s=0.0)

    tqdm.write(f"Found {len(files)} file(s) to process.\n")

    start = time.perf_counter()
    ok = 0
    skipped = 0
    failed = 0
    results: list[FileResult] = []
    converter_times: dict[str, float] = {}
    total_files = len(files)

    def _notify(current: int, filename: str, phase: str):
        if progress_callback:
            try:
                progress_callback(current, total_files, filename, phase)
            except Exception:
                pass

    if jobs > 1:
        tqdm.write(f"Using {jobs} parallel workers.\n")
        executor = ThreadPoolExecutor(max_workers=jobs)
        futures = {}

        def _finished():
            """Futures in completion order; on cancel: drop the queue, then
            yield only the files already running (they finish atomically).
            NB: executor.shutdown(cancel_futures=True) deadlocks as_completed —
            futures cancelled that way never wake its waiter."""
            pending = set(futures)
            for f in as_completed(futures):
                pending.discard(f)
                yield f
                if cancel_event and cancel_event.is_set():
                    break
            for f in pending:
                f.cancel()  # only succeeds for queued, not running, futures
            yield from (f for f in pending if not f.cancelled())

        try:
            for path in files:
                if cancel_event and cancel_event.is_set():
                    break
                future = executor.submit(
                    convert_file, path, output_dir, force=force, dry_run=dry_run
                )
                futures[future] = path

            # Notify that all files are submitted (shows total count immediately)
            _notify(0, f"{total_files} files queued", "converting")

            completed = 0
            for future in _finished():
                path = futures[future]
                completed += 1
                try:
                    fr = future.result()
                except Exception as e:
                    fr = FileResult(path=path, status="failed", converter="—",
                                    format_detected="unknown", error=str(e),
                                    elapsed_s=0)
                results.append(fr)
                if fr.status == "ok":
                    ok += 1
                elif fr.status == "skipped":
                    skipped += 1
                else:
                    failed += 1
                conv = fr.converter
                if conv and conv != "—":
                    converter_times[conv] = converter_times.get(conv, 0.0) + fr.elapsed_s
                phase = "done" if fr.status in ("ok", "skipped") else "failed"
                _notify(completed, path.name, phase)
        except KeyboardInterrupt:
            # Ctrl+C: drop the queue, wait only for files already running
            for f in futures:
                f.cancel()
            raise
        finally:
            executor.shutdown(wait=True)
    else:
        # Sequential mode: report "converting" before each file
        for i, path in enumerate(files):
            if cancel_event and cancel_event.is_set():
                break
            _notify(i + 1, path.name, "converting")
            fr = convert_file(path, output_dir, force=force, dry_run=dry_run)
            results.append(fr)
            if fr.status == "ok":
                ok += 1
            elif fr.status == "skipped":
                skipped += 1
            else:
                failed += 1
            conv = fr.converter
            if conv and conv != "—":
                converter_times[conv] = converter_times.get(conv, 0.0) + fr.elapsed_s
            phase = "done" if fr.status in ("ok", "skipped") else "failed"
            _notify(i + 1, path.name, phase)

    elapsed = time.perf_counter() - start
    return BatchSummary(
        total=len(files), ok=ok, skipped=skipped, failed=failed,
        elapsed_s=elapsed, results=results, converter_times=converter_times,
    )
