"""XZ archive → delegate to inner format (ADR-003: Single-Book).

Decompresses with Python lzma (built-in), detects inner format via
magic bytes, renames with correct extension, delegates.
"""

import tempfile
from pathlib import Path

from ..detector import FormatName, detect_format, classify_pdf
from ..security import safe_decompress_xz
from . import Converter, register, find_converter


@register
class _XzArchiveConverter:
    label = "XZ archive (lzma decompress + delegate)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt == "xz"

    @staticmethod
    def check_deps() -> list[str]:
        try:
            import lzma  # noqa: F401
        except ImportError:
            return ["Python lzma module not available."]
        return []

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        with tempfile.TemporaryDirectory(prefix="mdmaker_xz_") as tmpdir:
            tmp = Path(tmpdir)

            # Safe decompression (ADR-003: Size-bomb protection)
            inner = safe_decompress_xz(path, tmp)

            # Detect inner format and delegate
            fmt = detect_format(inner)
            if fmt == "pdf_text":
                fmt = classify_pdf(inner)
            if fmt == "unknown":
                # Magic-byte detection already applied in safe_decompress_xz;
                # retry with the renamed file
                fmt = detect_format(inner)

            converter = find_converter(fmt)
            if converter is None:
                raise ValueError(
                    f"No converter for inner format '{fmt}' "
                    f"from XZ archive: {path.name}"
                )

            result = converter.convert(inner, output_dir)

            md_path = output_dir / (path.stem + ".md")
            if result != md_path:
                result.rename(md_path)
            return md_path
