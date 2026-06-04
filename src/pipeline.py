"""Pipeline orchestrator — detection → routing → conversion (ADR-001).

Binds converters via the registry, classifies PDFs, and manages
parallel execution (ADR-006: ThreadPoolExecutor for I/O-bound work).
"""

import time
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from .detector import detect_format, classify_pdf
from .converters import find_converter, REGISTRY


def check_all_dependencies() -> dict[str, list[str]]:
    """Check dependencies for all registered converters.

    Returns:
        Dict mapping converter label → list of missing-dependency messages.
        Empty dict = everything ready.
    """
    issues: dict[str, list[str]] = {}
    for conv in REGISTRY:
        missing = conv.check_deps()
        if missing:
            issues[conv.label] = missing
    return issues


def collect_files(paths: list[Path], recursive: bool = False) -> list[Path]:
    """Expand directories into a flat, deduplicated list of supported files."""
    SUPPORTED = {
        ".epub", ".mobi", ".azw", ".azw3", ".prc",
        ".pdf", ".doc", ".docx", ".djvu", ".chm",
        ".xz", ".zip",
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
        # Directory
        pattern = "**/*" if recursive else "*"
        for f in sorted(p.glob(pattern)):
            if f.is_file() and f.suffix.lower() in SUPPORTED:
                key = str(f.resolve())
                if key not in seen:
                    seen.add(key)
                    files.append(f)

    return files


def convert_file(
    path: Path, output_dir: Path,
    force: bool = False, dry_run: bool = False,
) -> Optional[Path]:
    """Convert one file through the full pipeline: detect → classify → route → convert."""
    # Step 1: Detect format
    fmt = detect_format(path)
    if fmt == "unknown":
        tqdm.write(f"[!] Unknown format: {path.name}")
        return None

    # Step 2: Classify PDFs (ADR-005)
    if fmt == "pdf_text":
        fmt = classify_pdf(path)
        if dry_run:
            tqdm.write(f"   [*] {path.name}: {fmt}")

    # Step 3: Find converter
    converter = find_converter(fmt)
    if converter is None:
        tqdm.write(f"[!] No converter for '{fmt}': {path.name}")
        return None

    # Step 4: Check if output exists
    md_path = output_dir / (path.stem + ".md")
    if md_path.exists() and md_path.stat().st_size > 100 and not force:
        return md_path

    if dry_run:
        tqdm.write(f"   [*] Would convert [{converter.label}]: {path.name}")
        return md_path

    # Step 5: Convert
    try:
        return converter.convert(path, output_dir)
    except Exception as e:
        tqdm.write(f"[FAIL] [{converter.label}]: {path.name} — {e}")
        return None


def convert_batch(
    paths: list[Path], output_dir: Path, *,
    force: bool = False, dry_run: bool = False,
    recursive: bool = False, jobs: int = 1,
) -> dict:
    """Convert a batch of files with progress bar and optional parallelism.

    ADR-006: ThreadPoolExecutor for I/O-bound formats. OCR
    (CPU-bound) spawns its own Tesseract processes externally.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    files = collect_files(paths, recursive=recursive)

    if not files:
        tqdm.write("No supported files found.")
        return {"total": 0, "ok": 0, "skipped": 0, "failed": 0, "elapsed_s": 0.0}

    tqdm.write(f"Found {len(files)} file(s) to process.\n")

    start = time.perf_counter()
    ok = 0; skipped = 0; failed = 0

    if jobs > 1:
        tqdm.write(f"Using {jobs} parallel workers.\n")
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            futures = {
                executor.submit(convert_file, p, output_dir, force=force, dry_run=dry_run): p
                for p in files
            }
            pbar = tqdm(total=len(files), unit="file", desc="Converting")
            for future in as_completed(futures):
                path = futures[future]
                pbar.set_postfix_str(path.name[:40])
                try:
                    result = future.result()
                    md_path = output_dir / (path.stem + ".md")
                    if dry_run:
                        pass
                    elif result is not None and result.exists() and result.stat().st_size > 100:
                        ok += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                pbar.update(1)
            pbar.close()
    else:
        pbar = tqdm(files, unit="file", desc="Converting")
        for path in pbar:
            pbar.set_postfix_str(path.name[:40])
            md_path = output_dir / (path.stem + ".md")
            existed = md_path.exists() and md_path.stat().st_size > 100
            result = convert_file(path, output_dir, force=force, dry_run=dry_run)
            if dry_run:
                continue
            elif result is not None and result.exists() and result.stat().st_size > 100:
                if existed and not force:
                    skipped += 1
                else:
                    ok += 1
            else:
                failed += 1

    elapsed = time.perf_counter() - start
    return {"total": len(files), "ok": ok, "skipped": skipped, "failed": failed, "elapsed_s": elapsed}
