"""EPUB / MOBI / PRC → Markdown via pure Python (ebooklib + BeautifulSoup).

Pure-Python pipeline that needs NO external tools:
    EPUB → extract HTML via zipfile + ebooklib → clean text via BeautifulSoup → Markdown.
    Binary MOBI/AZW3/PRC/LIT go through kindle.py (Calibre → EPUB → this module).

Why replace Calibre:
    - Calibre ``ebook-convert`` spawns terminal windows on Windows.
    - It's a heavy dependency (~500 MB) that users shouldn't need for EPUB.
    - Pure Python is faster, simpler, and never pops up windows.
"""

import zipfile
import re
import tempfile
from pathlib import Path

from ..detector import FormatName
from . import Converter, register, sanitize_filename


def _extract_text_from_html(html_content: str) -> str:
    """Extract clean, readable text from HTML content using BeautifulSoup."""
    from bs4 import BeautifulSoup

    # Suppress XMLParsedAsHTMLWarning — EPUBs often contain XHTML
    import warnings
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

    # Detect XHTML (XML-based) vs HTML
    if html_content.strip().startswith("<?xml") or 'xmlns="' in html_content[:500]:
        # Use XML parser for XHTML documents
        try:
            soup = BeautifulSoup(html_content, "xml")
        except Exception:
            soup = BeautifulSoup(html_content, "lxml")
    else:
        soup = BeautifulSoup(html_content, "lxml")
    # Remove script, style, nav, header, footer
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()

    # Get text with newline separation
    text = soup.get_text(separator="\n", strip=True)

    # Collapse excessive whitespace
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _epub_to_text(path: Path) -> str:
    """Extract readable text from an EPUB file using ebooklib.

    EPUB 2 and EPUB 3 are both supported. Handles:
    - Invalid ZIP structures (some EPUBs have trailing data)
    - Missing nav/NCX (falls back to reading all HTML in spine order)
    - Encoded content (utf-8, cp1252, latin-1)
    """
    from ebooklib import epub, ITEM_DOCUMENT

    # ebooklib needs the file path as a string, but some EPUBs have
    # structural quirks. We try ebooklib first, then fall back to raw zipfile.
    try:
        book = epub.read_epub(str(path), options={"ignore_ncx": False})
    except Exception:
        # Fallback: raw zipfile extraction
        return _epub_fallback_zip(path)

    chapters = []
    total_chars = 0

    # Try spine order first (EPUB 3)
    spine_items = []
    for item_id, _linear in book.spine:
        try:
            item = book.get_item_with_id(item_id)
            if item and item.get_type() == ITEM_DOCUMENT:
                spine_items.append(item)
        except Exception:
            continue

    # Fallback: iterate all document items in order
    if not spine_items:
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            spine_items.append(item)

    for item in spine_items:
        try:
            content = item.get_content()
        except Exception:
            continue

        # Try UTF-8 first, then common encodings
        for encoding in ["utf-8", "cp1252", "latin-1", "iso-8859-1"]:
            try:
                html = content.decode(encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            # Last resort: replace errors
            html = content.decode("utf-8", errors="replace")

        text = _extract_text_from_html(html)
        if text and len(text) > 50:  # Skip tiny fragments
            chapters.append(text)
            total_chars += len(text)

    if total_chars == 0:
        raise ValueError(f"No readable text extracted from EPUB: {path.name}")

    return "\n\n".join(chapters)


def _epub_fallback_zip(path: Path) -> str:
    """Raw ZIP fallback: extract HTML files directly from the EPUB container.

    EPUB files are ZIP archives. This handles malformed EPUBs that
    ebooklib rejects by reading the HTML content directly.
    """
    chapters = []
    total_chars = 0

    with tempfile.TemporaryDirectory(prefix="mdmaker_epub_") as tmpdir:
        tmp = Path(tmpdir)
        try:
            with zipfile.ZipFile(str(path), "r") as zf:
                zf.extractall(str(tmp))
        except zipfile.BadZipFile as e:
            raise ValueError(f"Not a valid ZIP/EPUB file: {path.name}") from e

        # Find all HTML/XHTML files, sorted by name (approximate reading order)
        html_files = sorted(
            list(tmp.rglob("*.html")) +
            list(tmp.rglob("*.htm")) +
            list(tmp.rglob("*.xhtml")) +
            list(tmp.rglob("*.xml"))
        )

        for hf in html_files:
            for encoding in ["utf-8", "cp1252", "latin-1", "iso-8859-1"]:
                try:
                    raw = hf.read_text(encoding=encoding)
                    break
                except (UnicodeDecodeError, UnicodeError, LookupError):
                    continue
            else:
                raw = hf.read_text(encoding="utf-8", errors="replace")

            text = _extract_text_from_html(raw)
            if text and len(text) > 50:
                chapters.append(text)
                total_chars += len(text)

    if total_chars == 0:
        raise ValueError(f"No readable text extracted from EPUB (ZIP fallback): {path.name}")

    return "\n\n".join(chapters)


@register
class _EpubConverter:
    label = "EPUB (ebooklib + BeautifulSoup)"

    @staticmethod
    def can_handle(fmt: FormatName) -> bool:
        return fmt == "epub"  # binary MOBI/PRC/LIT → kindle.py

    @staticmethod
    def check_deps() -> list[str]:
        missing = []
        try:
            import ebooklib  # noqa: F401
        except ImportError:
            missing.append(
                "ebooklib not installed.\n"
                "  Fix:  pip install ebooklib"
            )
        try:
            import bs4  # noqa: F401
        except ImportError:
            missing.append(
                "beautifulsoup4 not installed.\n"
                "  Fix:  pip install beautifulsoup4 lxml"
            )
        return missing

    @staticmethod
    def convert(path: Path, output_dir: Path) -> Path:
        # Step 1: MOBI/PRC → try as ebooklib first (many are ZIP-based)
        # If that fails, we attempt a ZIP-based fallback
        text = _epub_to_text(path)

        # Step 2: Write Markdown
        md_path = output_dir / (sanitize_filename(path.stem) + ".md")
        title = sanitize_filename(path.stem)
        md_content = (
            f"# {title}\n\n"
            f"> Converted from {path.suffix.upper().lstrip('.')} "
            f"via ebooklib + BeautifulSoup\n\n"
            f"{text}"
        )
        md_path.write_text(md_content, encoding="utf-8")
        return md_path
