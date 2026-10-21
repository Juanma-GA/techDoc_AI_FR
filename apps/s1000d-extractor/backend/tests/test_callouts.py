"""Detection semantique des warning/caution associes aux pictogrammes PDF."""

from __future__ import annotations

from app.core.notes_detector import classify_admonition
from app.core.structure_infer import build_ir
from app.core.ir import RawBlock


def test_human_harm_has_priority_over_material_harm() -> None:
    kind, confidence, rationale = classify_admonition(
        "Risque de choc electrique et de dommages materiels."
    )

    assert kind == "warning"
    assert confidence > 0.9
    assert "personne" in rationale or "electrique" in rationale


def test_material_harm_is_caution() -> None:
    kind, confidence, _ = classify_admonition(
        "Ne pas endommager le moteur et ne pas retirer la graisse protectrice.",
    )

    assert kind == "caution"
    assert confidence > 0.8


def test_pictogram_block_becomes_reviewable_admonition() -> None:
    root = build_ir([RawBlock(
        text="L’utilisateur est responsable de la classification de la zone.",
        page=1,
        is_pictogram=True,
    )])

    node = next(node for node in root.walk() if node.kind == "admonition")
    assert node.admonition == "warning"
    assert node.is_pictogram is True
    assert node.confidence < 0.6
    assert "verification humaine" in node.admonition_rationale
