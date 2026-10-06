"""Detection semantique des warning/caution associes aux pictogrammes PDF."""

from __future__ import annotations

from pathlib import Path

from app.core.notes_detector import classify_admonition
from app.core.structure_infer import build_ir
from app.core.ir import RawBlock
from app.parsers.pdf_parser import parse_pdf_pages


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


def test_weg_recommendations_page_has_semantic_callouts() -> None:
    pdf_path = Path(__file__).resolve().parents[2] / "WEG-WMO.pdf"
    pages = parse_pdf_pages(pdf_path)
    blocks = [block for page in pages for block in page.blocks]
    root = build_ir(blocks)

    callouts = [
        node for node in root.walk()
        if node.kind == "admonition" and node.is_pictogram and node.page == 6
    ]
    assert [node.admonition for node in callouts] == [
        "warning", "warning", "note", "warning", "warning",
    ]
    assert any(node.confidence < 0.6 for node in callouts)