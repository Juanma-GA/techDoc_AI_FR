"""`rules_engine.materialize` integration with `search_for`-driven bboxes.

Two scenarios:
- The raw suggestion's `original` is present on the page → bbox carries
  the exact (x0,y0,x1,y1) of the occurrence + page dimensions.
- The raw `original` is absent or empty → bbox stores `x0=None` so the
  front-end can skip rendering an overlay (rather than the historic
  `(0,0,1,1)` minuscule fallback).
"""

from __future__ import annotations

import json
import uuid

import fitz

from app.checks.raw import RawSuggestion
from app.core.rules_engine import materialize
from app.parsers.pdf_parser import parse_pdf


def _make_pdf(tmp_path) -> str:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 80), "must be removed", fontname="helv", fontsize=12)
    page.insert_text((50, 200), "must be cleaned", fontname="helv", fontsize=12)
    out = tmp_path / "doc.pdf"
    doc.save(str(out))
    doc.close()
    return str(out)


def test_materialize_uses_search_for_when_src_path_present(tmp_path) -> None:
    path = _make_pdf(tmp_path)
    parsed = parse_pdf(path)
    raws = [
        RawSuggestion(
            rule_kind="custom", rule_code="MUST_TO_SHALL", severity="warning",
            message="prefer 'shall'", original="must", proposed="shall",
            page=1, span=(11, 15),
        ),
        RawSuggestion(
            rule_kind="custom", rule_code="MUST_TO_SHALL", severity="warning",
            message="prefer 'shall'", original="must", proposed="shall",
            page=1, span=(0, 4),
        ),
    ]
    rows = materialize(raws, parsed, uuid.uuid4(), uuid.uuid4(), src_path=path)
    assert len(rows) == 2
    box0 = json.loads(rows[0].bbox)
    box1 = json.loads(rows[1].bbox)
    # span_index increments for the same (page, original) pair.
    assert rows[0].span_index == 0
    assert rows[1].span_index == 1
    # Both bboxes are filled, with page metadata.
    for box in (box0, box1):
        assert isinstance(box["x0"], (int, float))
        assert box["x1"] > box["x0"]
        assert box["y1"] > box["y0"]
        assert box["page_w"] == 400.0
        assert box["page_h"] == 300.0
        assert box["page_rotation"] == 0
    # The two occurrences sit on different lines.
    assert abs(box0["y0"] - box1["y0"]) > 50


def test_materialize_returns_null_bbox_for_missing_text(tmp_path) -> None:
    path = _make_pdf(tmp_path)
    parsed = parse_pdf(path)
    raws = [
        RawSuggestion(
            rule_kind="custom", rule_code="X", severity="warning",
            message="m", original="nonexistent token", proposed="x",
            page=1, span=(0, 17),
        ),
    ]
    rows = materialize(raws, parsed, uuid.uuid4(), uuid.uuid4(), src_path=path)
    box = json.loads(rows[0].bbox)
    assert box["x0"] is None
    assert box["page_w"] == 400.0  # page metadata stays available


def test_materialize_without_src_path_uses_legacy_span_walk(tmp_path) -> None:
    """Backward-compat: when no src_path is provided (older callers, tests
    that don't rebuild the PDF), the engine must still produce something
    usable via the legacy heuristic — no exception raised."""
    path = _make_pdf(tmp_path)
    parsed = parse_pdf(path)
    raws = [
        RawSuggestion(
            rule_kind="custom", rule_code="X", severity="warning",
            message="m", original="must", proposed="shall",
            page=1, span=(0, 4),
        ),
    ]
    rows = materialize(raws, parsed, uuid.uuid4(), uuid.uuid4(), src_path=None)
    assert len(rows) == 1
    box = json.loads(rows[0].bbox)
    # No page metadata when src_path is missing.
    assert box.get("page_w") in (None, 0, 0.0)
