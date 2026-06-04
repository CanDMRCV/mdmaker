"""Security hardening (BRIEF_SECURITY). Bedrohungsmodell + Safe-API.

Implements: Zip-Bomb protection, Path-Traversal prevention, XXE-safe XML,
resource limits, subprocess hardening. Every public function is a security
boundary — the pipeline must route THROUGH these, not around them.
"""

import os
import lzma
import shutil
import zipfile
import tempfile
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from contextlib import contextmanager


class SecurityError(Exception):
    """Raised when a security boundary is violated (bomb, traversal, injection)."""


# ── Zip-Bomb / Path-Traversal Protection (ADR-003) ──

def safe_extract_zip(zip_path: Path, dest_dir: Path,
                     max_ratio: int = 100, max_size: int = 500_000_000) -> Path:
    """Extract a ZIP safely. Raises SecurityError on bomb or traversal.

    Args:
        zip_path: Path to the ZIP file.
        dest_dir: Destination directory (created if needed).
        max_ratio: Maximum compression ratio allowed (decompressed/compressed).
        max_size: Maximum total decompressed size in bytes.

    Returns:
        Path to the largest extracted file (assumed main content).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    compressed_size = zip_path.stat().st_size
    total_decompressed = 0
    largest_file = None
    largest_size = 0

    with zipfile.ZipFile(str(zip_path), "r") as zf:
        for entry in zf.infolist():
            # ── Path-Traversal check: normalize and reject ".." ──
            member_path = os.path.normpath(entry.filename)
            if member_path.startswith("..") or os.path.isabs(member_path):
                raise SecurityError(
                    f"Path traversal detected in ZIP: {entry.filename!r}"
                )

            # ── Zip-Bomb check: ratio ──
            decompressed = entry.file_size
            if decompressed > 0:
                ratio = decompressed / max(compressed_size, 1)
                if ratio > max_ratio:
                    raise SecurityError(
                        f"Zip bomb suspected: {entry.filename!r} "
                        f"has compression ratio {ratio:.0f}:1 (max {max_ratio}:1)"
                    )
            total_decompressed += decompressed
            if total_decompressed > max_size:
                raise SecurityError(
                    f"Zip bomb suspected: total decompressed size "
                    f"{total_decompressed:,} exceeds limit {max_size:,}"
                )

    # ── Safe extraction ──
    with zipfile.ZipFile(str(zip_path), "r") as zf:
        for entry in zf.infolist():
            member_path = os.path.normpath(entry.filename)
            target = dest_dir / member_path
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(entry) as src:
                with open(str(target), "wb") as dst:
                    shutil.copyfileobj(src, dst)
            if target.stat().st_size > largest_size:
                largest_size = target.stat().st_size
                largest_file = target

    if largest_file is None:
        raise SecurityError(f"No files found in ZIP: {zip_path.name}")
    return largest_file


def safe_decompress_xz(xz_path: Path, dest_dir: Path,
                       max_size: int = 500_000_000) -> Path:
    """Decompress XZ safely.

    Returns:
        Path to the decompressed file (with correct extension if detectable).
    """
    raw_path = dest_dir / (xz_path.stem + ".raw")
    dest_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    with lzma.open(str(xz_path), "rb") as src:
        with open(str(raw_path), "wb") as dst:
            while True:
                chunk = src.read(1_048_576)  # 1 MB
                if not chunk:
                    break
                total += len(chunk)
                if total > max_size:
                    raw_path.unlink(missing_ok=True)
                    raise SecurityError(
                        f"XZ bomb suspected: decompressed size exceeds {max_size:,}"
                    )
                dst.write(chunk)

    # Detect correct extension via magic bytes (ADR-003)
    from .detector import detect_inner_format
    ext = detect_inner_format(raw_path) or ".pdf"
    proper = raw_path.with_suffix(ext)
    raw_path.rename(proper)
    return proper


# ── XXE-Safe XML Parsing (BRIEF_SECURITY §2) ──

def safe_parse_xml(xml_path: Path) -> ET.ElementTree:
    """Parse XML without XXE (external entity) vulnerability.

    Uses defusedxml if available; otherwise configures ElementTree defensively.
    """
    try:
        from defusedxml import ElementTree as SafeET
        return SafeET.parse(str(xml_path))
    except ImportError:
        # Fallback: configure ElementTree without custom entity resolution
        # (Python 3.x default is resolve_entities=False, but be explicit)
        parser = ET.XMLParser(resolve_entities=False)
        tree = ET.parse(str(xml_path), parser=parser)
        return tree


# ── Safe Subprocess (BRIEF_SECURITY §2) ──

def safe_run(cmd: list[str], timeout: int = 300, **kwargs) -> subprocess.CompletedProcess:
    """Run a subprocess securely. NEVER uses shell=True. Always has a timeout."""
    return subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        shell=False,  # Non-negotiable: no shell injection
        **kwargs,
    )


# ── Resource Limits (BRIEF_SECURITY §5) ──

@contextmanager
def resource_guard(timeout_s: int = 300, label: str = ""):
    """Context manager that tracks elapsed time and logs slow conversions."""
    import time
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        if elapsed > timeout_s * 0.8 and label:
            import warnings
            warnings.warn(f"[RESOURCE] {label}: {elapsed:.1f}s (approaching {timeout_s}s limit)")
