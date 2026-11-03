"""Regression: Kindle/LIT detection + routing, thread-safe converter registry.

Bugs (AUFRUHR run, 2026-11-03):
- MOBI/AZW3/LIT were routed to the EPUB converter → "Not a valid ZIP/EPUB file".
- With -j >1 workers saw a half-loaded registry → "No converter for 'epub'".
"""

import subprocess
import sys
from pathlib import Path

from src.detector import detect_format
from src.converters import find_converter

ROOT = Path(__file__).resolve().parents[1]


def _palmdb(tmp_path: Path, name: str, type_creator: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(b"x" * 60 + type_creator + b"\0" * 200)
    return p


def test_mobi_magic_beats_wrong_extension(tmp_path):
    assert detect_format(_palmdb(tmp_path, "book.epub", b"BOOKMOBI")) == "mobi"
    assert detect_format(_palmdb(tmp_path, "book.azw3", b"BOOKMOBI")) == "mobi"
    assert detect_format(_palmdb(tmp_path, "old.prc", b"TEXtREAd")) == "prc"


def test_lit_magic(tmp_path):
    p = tmp_path / "book.epub"  # real case: .lit saved as .epub
    p.write_bytes(b"ITOLITLS" + b"\0" * 200)
    assert detect_format(p) == "lit"


def test_routing():
    assert "Calibre" in find_converter("mobi").label
    assert "Calibre" in find_converter("lit").label
    assert "Calibre" not in find_converter("epub").label


def test_registry_threadsafe_in_fresh_process():
    # Fresh interpreter: the registry must be cold for the race to show.
    code = (
        "from concurrent.futures import ThreadPoolExecutor\n"
        "from src.converters import find_converter\n"
        "with ThreadPoolExecutor(16) as ex:\n"
        "    r = list(ex.map(lambda f: find_converter(f), ['epub', 'mobi', 'pdf_text', 'docx'] * 8))\n"
        "assert all(r), r\n"
    )
    for _ in range(5):
        subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        test_mobi_magic_beats_wrong_extension(Path(d))
        test_lit_magic(Path(d))
    test_routing()
    test_registry_threadsafe_in_fresh_process()
    print("OK")
