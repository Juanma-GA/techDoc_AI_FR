"""Image extraction + vision_checks pipeline (Mistral calls mocked)."""

from __future__ import annotations

from unittest.mock import patch

import fitz
import pytest

from app.checks import vision_checks
from app.core import mistral_vision
from app.core.errors import AppError
from app.parsers.pdf_parser import extract_images


def _pdf_with_image(tmp_path, with_caption: bool = True) -> str:
    """Build a one-page PDF that embeds a tiny coloured rectangle as an
    image, optionally followed by a 'Figure 1 — Sample' caption line."""
    # Build a 32×24 red PNG via PyMuPDF so the image bytes are real PDF
    # data, not a hand-crafted blob that PyMuPDF might reject.
    img = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 32, 24))
    img.set_rect(img.irect, (220, 30, 30))
    png_bytes = img.tobytes("png")

    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_image(fitz.Rect(50, 50, 150, 130), stream=png_bytes)
    if with_caption:
        page.insert_text((50, 145), "Figure 1 — Échantillon", fontname="helv", fontsize=10)
    out = tmp_path / "pdf_with_image.pdf"
    doc.save(str(out))
    doc.close()
    return str(out)


def test_extract_images_returns_image_with_caption(tmp_path) -> None:
    path = _pdf_with_image(tmp_path, with_caption=True)
    imgs = extract_images(path, max_per_doc=20)
    assert len(imgs) == 1
    img = imgs[0]
    assert img.page == 1
    assert img.bytes  # non-empty bytes
    assert img.mime == "image/png"
    assert img.caption_nearby.lower().startswith("figure 1")


def test_extract_images_no_caption_returns_empty_string(tmp_path) -> None:
    path = _pdf_with_image(tmp_path, with_caption=False)
    imgs = extract_images(path, max_per_doc=20)
    assert len(imgs) == 1
    assert imgs[0].caption_nearby == ""


def test_extract_images_cap_enforced(tmp_path) -> None:
    """`max_per_doc` is respected — cost guard for the vision pipeline."""
    doc = fitz.open()
    page = doc.new_page(width=400, height=600)
    for i in range(5):
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 16, 16))
        pix.set_rect(pix.irect, (i * 35, 0, 255 - i * 30))
        png = pix.tobytes("png")
        page.insert_image(fitz.Rect(20, 20 + i * 100, 80, 80 + i * 100), stream=png)
    out = tmp_path / "five.pdf"
    doc.save(str(out))
    doc.close()

    imgs = extract_images(str(out), max_per_doc=3)
    assert len(imgs) == 3

    warnings: list[str] = []
    vision_checks.run(
        db=None,  # type: ignore[arg-type]
        src_path=str(out),
        max_images=3,
        enable_mistral=False,
        warnings=warnings,
    )
    assert len(warnings) == 1
    assert "images restantes" in warnings[0]


def test_vision_checks_emits_no_caption_when_caption_missing(tmp_path) -> None:
    """Structural check `FIGURE_NO_CAPTION` fires without any Mistral call."""
    path = _pdf_with_image(tmp_path, with_caption=False)
    # Bypass Mistral entirely with `enable_mistral=False`.
    raws = vision_checks.run(db=None, src_path=path, enable_mistral=False)  # type: ignore[arg-type]
    assert any(r.rule_code == "FIGURE_NO_CAPTION" for r in raws)
    assert all(r.proposed == "" for r in raws)  # detection-only


def test_vision_checks_skips_no_caption_when_present(tmp_path) -> None:
    path = _pdf_with_image(tmp_path, with_caption=True)
    raws = vision_checks.run(db=None, src_path=path, enable_mistral=False)  # type: ignore[arg-type]
    assert all(r.rule_code != "FIGURE_NO_CAPTION" for r in raws)


def test_vision_checks_pipeline_with_mocked_mistral(tmp_path) -> None:
    """End-to-end : when Mistral returns a non-compliant verdict, a vision
    suggestion is emitted with the correct rule_code, severity, message."""
    path = _pdf_with_image(tmp_path, with_caption=True)

    fake_compliance = {
        "results": [
            {"id": "FIGURE_LEGIBLE", "compliant": False, "evidence": "Trop pixelisé."},
            {"id": "FIGURE_HAS_NUMBERING", "compliant": True, "evidence": "OK."},
        ]
    }

    with patch.object(vision_checks, "check_figure_compliance", return_value=fake_compliance), \
         patch.object(vision_checks, "describe_image", return_value="Un échantillon rouge."):
        raws = vision_checks.run(db=None, src_path=path, enable_mistral=True)  # type: ignore[arg-type]

    codes = [r.rule_code for r in raws]
    assert "FIGURE_LEGIBLE" in codes
    assert "FIGURE_HAS_NUMBERING" not in codes  # compliant=True → no suggestion
    legible = next(r for r in raws if r.rule_code == "FIGURE_LEGIBLE")
    assert legible.severity == "warning"
    assert "Trop pixelisé" in legible.message
    assert legible.proposed == ""  # detection-only


def test_invalid_vision_json_is_incomplete_without_retaining_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response_marker = "SYNTHETIC-RAW-VISION-RESPONSE"
    monkeypatch.setattr(mistral_vision, "_call_mistral_vision", lambda *_args, **_kwargs: response_marker)

    with pytest.raises(AppError) as exc_info:
        mistral_vision.check_figure_compliance(object(), b"synthetic-image", [{"id": "RULE"}])

    assert exc_info.value.code == "VISION_RESPONSE_INVALID"
    assert response_marker not in exc_info.value.message


def test_description_failure_marks_vision_coverage_incomplete(tmp_path) -> None:
    path = _pdf_with_image(tmp_path, with_caption=True)
    warnings: list[str] = []

    with patch.object(vision_checks, "check_figure_compliance", return_value={"results": []}), \
         patch.object(vision_checks, "describe_image", side_effect=AppError("VISION_CALL_FAILED", "synthetic")):
        result = vision_checks.run(
            db=None,  # type: ignore[arg-type]
            src_path=path,
            enable_mistral=True,
            warnings=warnings,
        )

    assert result == []
    assert len(warnings) == 1
    assert "couverture est réduite" in warnings[0]


def test_run_all_respects_vision_override(tmp_path) -> None:
    """`vision_enabled_override=False` skips the vision pipeline even
    when the global `vision.enabled` flag is on. Conversely, `=True`
    runs it even when the global flag is off."""
    from unittest.mock import MagicMock, patch as _patch

    from app.core import rules_engine
    from app.parsers.pdf_parser import parse_pdf

    path = _pdf_with_image(tmp_path, with_caption=False)
    parsed = parse_pdf(path)

    class _DocStub:
        target_unit_system = "auto"

    fake_db = MagicMock()
    fake_db.scalars.return_value = []

    with _patch.object(rules_engine, "_merge_catalogs", return_value=[]), \
         _patch.object(rules_engine, "_run_ai_custom", return_value=[]), \
         _patch.object(rules_engine, "_enrich_with_ai", side_effect=lambda raws, db, **_kwargs: raws), \
         _patch.object(rules_engine, "get_vision_enabled", return_value=True) as mock_get_enabled, \
         _patch.object(rules_engine.vision_checks, "run", return_value=[]) as mock_vision_run, \
         _patch.object(rules_engine.custom_rules, "run", return_value=[]), \
         _patch.object(rules_engine.units_check, "run", return_value=[]):

        # Case 1: global=ON, override=False → vision NOT called.
        rules_engine.run_all(
            parsed, _DocStub(), fake_db, None,  # type: ignore[arg-type]
            src_path=path, vision_enabled_override=False,
        )
        assert mock_vision_run.call_count == 0

        # Case 2: global=ON, override=None → uses global (calls vision).
        rules_engine.run_all(
            parsed, _DocStub(), fake_db, None,  # type: ignore[arg-type]
            src_path=path, vision_enabled_override=None,
        )
        assert mock_vision_run.call_count == 1
        mock_get_enabled.assert_called()

        # Case 3: global=OFF, override=True → vision called.
        mock_get_enabled.return_value = False
        rules_engine.run_all(
            parsed, _DocStub(), fake_db, None,  # type: ignore[arg-type]
            src_path=path, vision_enabled_override=True,
        )
        assert mock_vision_run.call_count == 2


def test_vision_checks_handles_mistral_error(tmp_path) -> None:
    """Mistral failure on one image is logged and skipped, the run goes on."""
    from app.core.errors import AppError

    path = _pdf_with_image(tmp_path, with_caption=True)
    with patch.object(
        vision_checks, "check_figure_compliance",
        side_effect=AppError("VISION_CALL_FAILED", "Mistral down", status_code=502),
    ):
        # No exception bubbles up — the run returns the structural results
        # only (none here since the caption is present).
        raws = vision_checks.run(db=None, src_path=path, enable_mistral=True)  # type: ignore[arg-type]
    # No vision suggestion emitted, but no exception either.
    assert all(r.rule_code == "FIGURE_NO_CAPTION" for r in raws)  # empty list is fine too
