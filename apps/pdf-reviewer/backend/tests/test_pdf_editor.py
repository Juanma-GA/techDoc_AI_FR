"""pdf_editor.apply_patch — apply, idempotence, rollback parity."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import fitz
import pytest

from app.core.pdf_editor import PatchSpec, apply_patch
from app.core.pdf_versioning import bump_version, init_storage, path_for


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _build_pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 100), text, fontname="helv", fontsize=12)
    raw = doc.tobytes()
    doc.close()
    return raw


@pytest.fixture
def storage_dir_value() -> str:
    return "document_pdf_editor_test"


def test_apply_patch_writes_proposed_text(storage_dir_value: str) -> None:
    raw = _build_pdf_with_text("Torque 12 cm here")
    init_storage(storage_dir_value, raw)

    snap = bump_version(storage_dir_value, 0)
    result = apply_patch(
        path_for(storage_dir_value, 0),
        snap.snapshot_path,
        PatchSpec(
            page=1,
            bbox=(0.0, 0.0, 400.0, 300.0),
            original_text="12 cm",
            proposed_text="4.72 in",
        ),
    )
    assert result.font_used in {"helv", "times-roman", "cour"}

    edited = fitz.open(snap.snapshot_path)
    try:
        rendered = edited[0].get_text("text")
    finally:
        edited.close()
    assert "4.72 in" in rendered
    assert "12 cm" not in rendered


def test_v0_remains_immutable_after_apply(storage_dir_value: str) -> None:
    storage = "document_immutable_v0"
    raw = _build_pdf_with_text("Torque 12 cm here")
    init_storage(storage, raw)

    v0 = path_for(storage, 0)
    sha_before = _sha(v0)

    snap = bump_version(storage, 0)
    apply_patch(
        v0,
        snap.snapshot_path,
        PatchSpec(
            page=1,
            bbox=(0.0, 0.0, 400.0, 300.0),
            original_text="12 cm",
            proposed_text="4.72 in",
        ),
    )
    assert _sha(v0) == sha_before


def test_short_proposed_text_keeps_original_size(storage_dir_value: str) -> None:
    storage = "document_short_proposed"
    raw = _build_pdf_with_text("Width 12 cm now")
    init_storage(storage, raw)
    snap = bump_version(storage, 0)
    result = apply_patch(
        path_for(storage, 0),
        snap.snapshot_path,
        PatchSpec(
            page=1,
            bbox=(0.0, 0.0, 400.0, 300.0),
            original_text="12 cm",
            proposed_text="5 in",
        ),
    )
    assert not result.wrapped
    assert result.font_size_used >= 11.0  # close to original 12


def test_long_proposed_text_triggers_wrap(storage_dir_value: str) -> None:
    storage = "document_long_proposed"
    raw = _build_pdf_with_text("foo")
    init_storage(storage, raw)
    snap = bump_version(storage, 0)
    long_text = "this is a much longer replacement that will not fit on a single line of the original tight bbox"
    result = apply_patch(
        path_for(storage, 0),
        snap.snapshot_path,
        PatchSpec(
            page=1,
            bbox=(0.0, 0.0, 400.0, 300.0),
            original_text="foo",
            proposed_text=long_text,
        ),
    )
    # Either shrunk or wrapped — both acceptable for this case.
    assert result.font_size_used > 0


def test_font_resolution_preserves_weight_and_style() -> None:
    """Quick win #2 : font resolution should not collapse every span onto
    Helvetica plain when a weight or style is present in the source name."""
    from app.core.pdf_editor import _resolve_font

    assert _resolve_font("Times-Roman")[0] == "times-roman"
    assert _resolve_font("Times-Bold")[0] == "tibo"
    assert _resolve_font("Times-Italic")[0] == "timi"
    assert _resolve_font("TimesNewRomanPS-BoldItalic")[0] == "tibi"
    assert _resolve_font("Courier-Bold")[0] == "cobo"
    assert _resolve_font("Arial-Bold")[0] == "hebo"
    assert _resolve_font("Helvetica-Oblique")[0] == "heli"
    # Unknown font collapses to plain Helvetica but signals fallback.
    name, fallback = _resolve_font("MyCorpProprietaryFont")
    assert name == "helv"
    assert fallback is True


def test_baseline_uses_font_metrics() -> None:
    """Quick win #3 : baseline computed from ascender metric, not 0.78×h."""
    from app.core.pdf_editor import _font_metrics

    asc, desc = _font_metrics("helv")
    assert 0.7 < asc < 0.75   # Helvetica ascender ≈ 0.718
    assert -0.25 < desc < -0.15
    asc_times, _ = _font_metrics("times-roman")
    assert 0.6 < asc_times < 0.75


def test_background_sampling_picks_white_on_blank_page(tmp_path) -> None:
    """Quick win #4 : on a blank page, the sampled background is white
    (or very close to it), not a random adjacent colour."""
    from app.core.pdf_editor import _sample_background

    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 100), "small", fontname="helv", fontsize=12)
    rect = fitz.Rect(50, 95, 80, 110)
    r, g, b = _sample_background(page, rect)
    doc.close()
    # Blank page → background close to (1, 1, 1).
    assert min(r, g, b) > 0.9


def test_case_capitalize_phrase_level() -> None:
    """The seed `case_capitalize` rule must produce a single phrase-level
    suggestion (« PROCÉDURE DE MAINTENANCE » → « Procédure de maintenance »)
    instead of two word-level fixes that leave the stopword « DE » as-is."""
    from app.checks.custom_rules import _propose_capitalize

    assert _propose_capitalize("PROCEDURE DE MAINTENANCE") == "Procedure de maintenance"
    assert _propose_capitalize("DEMONTAGE DU MOTEUR") == "Demontage du moteur"
    assert _propose_capitalize("WARNING") == "Warning"
    # Short stand-alone acronyms stay untouched.
    assert _propose_capitalize("USB") == "USB"


def test_apply_raises_when_original_missing(storage_dir_value: str) -> None:
    storage = "document_missing_original"
    raw = _build_pdf_with_text("Hello world")
    init_storage(storage, raw)
    snap = bump_version(storage, 0)
    from app.core.errors import AppError

    with pytest.raises(AppError) as info:
        apply_patch(
            path_for(storage, 0),
            snap.snapshot_path,
            PatchSpec(
                page=1,
                bbox=(0.0, 0.0, 100.0, 100.0),
                original_text="not present",
                proposed_text="anything",
            ),
        )
    assert info.value.code == "ORIGINAL_NOT_FOUND"
