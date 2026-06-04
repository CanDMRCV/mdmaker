"""PDF (text layer) → Markdown via pdfplumber (ADR-001).

pdfplumber handles tables, columns, and text flow. Quality: Good.
Font artifacts on very old PDFs — logged as metadata.
"""

from pathlib import Path

from ..detector import FormatName
from . import Converter, register


@register
class _PdfTextConverter:
    label = "PDF text (pdfplumber)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt == "pdf_text"

    @staticmethod
    def check_deps() -> list[str]:
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            return ["pdfplumber not installed. Fix: pip install pdfplumber"]
        return []

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            pages = pdf.pages
            parts = []
            total_chars = 0

            for i, page in enumerate(pages):
                text = page.extract_text()
                if text:
                    parts.append(f"\n## Page {i + 1}\n\n{text}\n")
                    total_chars += len(text)

        md_path = output_dir / (path.stem + ".md")
        title = path.stem
        header = (
            f"# {title}\n\n"
            f"> {len(pages)} pages · {total_chars:,} chars · "
            f"Converted via pdfplumber\n\n"
        )
        md_path.write_text(header + "\n".join(parts), encoding="utf-8")
        return md_path
