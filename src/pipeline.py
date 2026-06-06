"""Pipeline orchestrator — detection → routing → conversion (ADR-001).

Binds converters via the registry, classifies PDFs, and manages
parallel execution (ADR-006: ThreadPoolExecutor for I/O-bound work).
v0.2.1: per-file results, timing, phase-aware progress for GUI.
"""

import sys
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

# Issue #3: Force UTF-8 stdout so tqdm bars render cleanly on Windows
# (cp1252/cp850 terminals show � artifacts for Unicode chars like ✓/─).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from tqdm import tqdm

from .detector import detect_format, classify_pdf
from .converters import find_converter, REGISTRY


@dataclass
class FileResult:
    """Per-file conversion result (A1: Fehler-Transparenz)."""
    path: Path
    status: str          # "ok" | "skipped" | "failed"
    converter: str        # converter label, e.g. "EPUB/MOBI/PRC (Calibre)"
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
    # Per-converter timing breakdown (B6)
    converter_times: dict[str, float] = field(default_factory=dict)


def check_all_dependencies() -> dict[str, list[str]]:
    issues: dict[str, list[str]] = {}
    for conv in REGISTRY:
        missing = conv.check_deps()
        if missing:
            issues[conv.label] = missing
    return issues


def collect_files(paths: list[Path], recursive: bool = False) -> list[Path]:
    SUPPORTED = {
        ".epub", ".mobi", ".azw", ".azw3", ".prc",
        ".pdf", ".doc", ".docx", ".djvu", ".chm", ".xz", ".zip",
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
    """Convert one file. Returns structured FileResult (A1, B6)."""
    t0 = time.perf_counter()
    fmt = detect_format(path)
    conv_label = "unknown"
    error = ""

    if fmt == "unknown":
        return FileResult(path=path, status="failed", converter="—",
                          format_detected="unknown", error="Unknown format",
                          elapsed_s=time.perf_counter() - t0)

    if fmt == "pdf_text":
        fmt = classify_pdf(path)

    converter = find_converter(fmt)
    if converter is None:
        return FileResult(path=path, status="failed", converter="—",
                          format_detected=fmt, error=f"No converter for '{fmt}'",
                          elapsed_s=time.perf_counter() - t0)
    conv_label = converter.label

    md_path = output_dir / (path.stem + ".md")
    if md_path.exists() and md_path.stat().st_size > 100 and not force:
        return FileResult(path=path, status="skipped", converter=conv_label,
                          format_detected=fmt, error="",
                          elapsed_s=time.perf_counter() - t0, output_md=md_path)

    if dry_run:
        return FileResult(path=path, status="skipped", converter=conv_label,
                          format_detected=fmt, error="[dry-run]",
                          elapsed_s=time.perf_counter() - t0)

    try:
        result = converter.convert(path, output_dir)
        elapsed = time.perf_counter() - t0
        ok = result is not None and result.exists() and result.stat().st_size > 100
        return FileResult(
            path=path, status="ok" if ok else "failed",
            converter=conv_label, format_detected=fmt,
            error="" if ok else "Output empty or missing",
            elapsed_s=elapsed, output_md=result if ok else None,
        )
    except Exception as e:
        return FileResult(path=path, status="failed", converter=conv_label,
                          format_detected=fmt, error=str(e)[:200],
                          elapsed_s=time.perf_counter() - t0)


def convert_batch(
    paths: list[Path], output_dir: Path, *,
    force: bool = False, dry_run: bool = False,
    recursive: bool = False, jobs: int = 1,
    progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> BatchSummary:
    """Convert a batch with progress, timing, and per-file results.

    progress_callback signature: (current, total, filename, phase)
    Phase is one of: "scanning", "converting", "ocr", "extracting", "done"
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    files = collect_files(paths, recursive=recursive)

    if not files:
        tqdm.write("No supported files found.")
        return BatchSummary(total=0, ok=0, skipped=0, failed=0, elapsed_s=0.0)

    tqdm.write(f"Found {len(files)} file(s) to process.\n")

    start = time.perf_counter()
    results: list[FileResult] = []
    converter_times: dict[str, float] = {}

    if jobs > 1:
        tqdm.write(f"Using {jobs} parallel workers.\n")
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            future_map = {
                executor.submit(convert_file, p, output_dir, force=force, dry_run=dry_run): p
                for p in files
            }
            pbar = tqdm(total=len(files), unit="file", desc="Converting")
            for future in as_completed(future_map):
                if cancel_event and cancel_event.is_set():
                    break
                path = future_map[future]
                try:
                    fr = future.result()
                except Exception as e:
                    fr = FileResult(path=path, status="failed", converter="—",
                                    format_detected="?", error=str(e)[:200],
                                    elapsed_s=0)
                results.append(fr)
                converter_times[fr.converter] = converter_times.get(fr.converter, 0) + fr.elapsed_s
                pbar.update(1)
                pbar.set_postfix_str(path.name[:40])

                # Phase-aware progress (A3)
                phase = _phase_for(fr)
                if progress_callback:
                    progress_callback(len(results), len(files), path.name, phase)
            pbar.close()
    else:
        pbar = tqdm(files, unit="file", desc="Converting")
        for path in pbar:
            if cancel_event and cancel_event.is_set():
                tqdm.write("[!] Canceled by user.")
                break
            pbar.set_postfix_str(path.name[:40])
            fr = convert_file(path, output_dir, force=force, dry_run=dry_run)
            results.append(fr)
            converter_times[fr.converter] = converter_times.get(fr.converter, 0) + fr.elapsed_s

            phase = _phase_for(fr)
            if progress_callback:
                progress_callback(len(results), len(files), path.name, phase)

    elapsed = time.perf_counter() - start
    ok = sum(1 for r in results if r.status == "ok")
    skipped = sum(1 for r in results if r.status == "skipped")
    failed = sum(1 for r in results if r.status == "failed")

    return BatchSummary(
        total=len(files), ok=ok, skipped=skipped, failed=failed,
        elapsed_s=elapsed, results=results, converter_times=converter_times,
    )


def _phase_for(fr: FileResult) -> str:
    """Derive a user-visible phase label from the result (A3)."""
    if fr.status == "ok":
        return "done"
    if fr.status == "failed":
        return "failed"
    if "OCR" in fr.converter or "scan" in fr.format_detected:
        return "ocr"
    if "CHM" in fr.converter or "ZIP" in fr.converter or "XZ" in fr.converter:
        return "extracting"
    return "converting"
