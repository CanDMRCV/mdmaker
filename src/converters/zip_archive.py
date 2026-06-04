"""ZIP archive → delegate to inner format (ADR-003: Single-Book).

Extracts safely (Zip-Bomb + Traversal protection), finds the largest
content file, delegates to the appropriate converter.
"""

import tempfile
from pathlib import Path

from ..detector import FormatName, detect_format, classify_pdf
from ..security import safe_extract_zip
from . import Converter, register, find_converter


@register
class _ZipArchiveConverter:
    label = "ZIP archive (safe extract + delegate)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt == "zip"

    @staticmethod
    def check_deps() -> list[str]:
        return []  # zipfile is built-in

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        with tempfile.TemporaryDirectory(prefix="mdmaker_zip_") as tmpdir:
            tmp = Path(tmpdir)

            # Safe extraction (ADR-003: Bomb + Traversal protection)
            main_file = safe_extract_zip(path, tmp)

            # Detect inner format and delegate
            fmt = detect_format(main_file)
            if fmt == "pdf_text":
                fmt = classify_pdf(main_file)

            converter = find_converter(fmt)
            if converter is None:
                raise ValueError(
                    f"No converter for inner format '{fmt}' "
                    f"from ZIP archive: {path.name}"
                )

            result = converter.convert(main_file, output_dir)

            # Rename to match the archive name
            md_path = output_dir / (path.stem + ".md")
            if result != md_path:
                result.rename(md_path)
            return md_path
