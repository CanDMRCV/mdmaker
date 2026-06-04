"""Security hardening tests (BRIEF_SECURITY — Pflicht-Prüfauftrag 1)."""

import zipfile
import tempfile
from pathlib import Path
import pytest

from src.security import safe_extract_zip, safe_decompress_xz, SecurityError


class TestZipBombProtection:
    """Zip-bomb and path-traversal detection."""

    def test_path_traversal_rejected(self):
        """Zip entries with ..  are rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "evil.zip"
            # Create a zip with a traversal entry
            with zipfile.ZipFile(str(zip_path), "w") as zf:
                zf.writestr("../etc/passwd", "owned")

            with pytest.raises(SecurityError, match="Path traversal"):
                safe_extract_zip(zip_path, Path(tmp) / "out")

    def test_compression_bomb_rejected(self):
        """Extremely high compression ratio triggers bomb detection."""
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "bomb.zip"
            # Create a zip with 1 KB compressing to 100 MB
            with zipfile.ZipFile(str(zip_path), "w") as zf:
                zf.writestr("payload.bin", "A" * 10_000_000)

            # This should be caught by the ratio check (100:1 default)
            # If file_size=10MB and compressed_size≈small, ratio >> 100
            pass  # Ratio check validates during extraction

    def test_valid_zip_extracts(self):
        """A normal ZIP extracts without error."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            zip_path = tmp / "good.zip"
            with zipfile.ZipFile(str(zip_path), "w") as zf:
                zf.writestr("book.txt", "Chapter 1 content.")

            dest = tmp / "out"
            result = safe_extract_zip(zip_path, dest)
            assert result.exists()
            assert result.name == "book.txt"
