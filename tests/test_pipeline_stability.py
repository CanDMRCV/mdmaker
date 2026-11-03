"""Stability/speed regressions for the pipeline (v0.5.2).

- Atomic output: a failing/aborted conversion leaves no half .md and no temp dir.
- Existing .md is skipped before detection (fast reruns).
- GUI cancel in parallel mode really stops the queue.
- PDF text: PyMuPDF is the primary engine.
"""

import threading
import time
from pathlib import Path

from src import pipeline


def _fake_pdf(p: Path) -> Path:
    p.write_bytes(b"%PDF-1.4\n" + b"x" * 200)  # passes magic + size check
    return p


class _Boom:
    label = "boom"

    @staticmethod
    def convert(path, out):
        (out / (path.stem + ".md")).write_text("half written", encoding="utf-8")
        raise RuntimeError("crash mid-write")


class _Slow:
    label = "slow"

    @staticmethod
    def convert(path, out):
        time.sleep(0.2)
        md = out / (path.stem + ".md")
        md.write_text("x" * 200, encoding="utf-8")
        return md


def test_failed_conversion_leaves_no_partial_output(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "find_converter", lambda fmt: _Boom)
    out = tmp_path / "out"; out.mkdir()
    fr = pipeline.convert_file(_fake_pdf(tmp_path / "a.pdf"), out)
    assert fr.status == "failed" and "crash mid-write" in fr.error
    assert list(out.iterdir()) == [], "no half .md, no .mdmaker_* temp dir"


def test_existing_md_skipped_before_detection(tmp_path, monkeypatch):
    def _never(_):
        raise AssertionError("detect_format must not run for existing output")
    monkeypatch.setattr(pipeline, "detect_format", _never)
    out = tmp_path / "out"; out.mkdir()
    (out / "a.md").write_text("done", encoding="utf-8")
    assert pipeline.convert_file(tmp_path / "a.pdf", out).status == "skipped"


def test_cancel_stops_parallel_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "find_converter", lambda fmt: _Slow)
    files = [_fake_pdf(tmp_path / f"b{i}.pdf") for i in range(20)]
    cancel = threading.Event()

    def _progress(cur, total, name, phase):
        if phase == "done":
            cancel.set()  # cancel after the first finished file

    s = pipeline.convert_batch(files, tmp_path / "out", jobs=2,
                               progress_callback=_progress, cancel_event=cancel)
    assert s.ok < 20, f"cancel ignored: {s.ok}/20 converted"


def test_pdf_primary_engine_is_pymupdf(tmp_path):
    import pymupdf
    from src.converters.pdf_text import _PdfTextConverter

    pdf = tmp_path / "t.pdf"
    doc = pymupdf.open(); doc.new_page().insert_text((72, 72), "hello world " * 20); doc.save(pdf); doc.close()
    out = tmp_path / "out"; out.mkdir()
    head = _PdfTextConverter.convert(pdf, out).read_text(encoding="utf-8").split("\n")[2]
    assert "via PyMuPDF" in head, head
