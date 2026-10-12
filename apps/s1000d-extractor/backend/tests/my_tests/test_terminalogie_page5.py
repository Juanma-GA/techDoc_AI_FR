"""Generation deterministe du DM descriptif TERMINOLOGIE (page 5).

Execution depuis ``backend`` :

    python tests/my_tests/test_terminalogie_page5.py

Le script suit les phases utiles de l'assistant pour un seul DM deja delimite :
extraction, nettoyage des zones de page, construction IR, choix du type,
resolution des balises, serialisation et validation non bloquante. Le XML est
imprime sur stdout et peut etre redirige vers un fichier.
"""

from __future__ import annotations

from pathlib import Path
import sys

from app.core import context_classifier, s1000d_guide, structure_infer
from app.core import validator
from app.core.resolver import resolve
from app.core.s1000d_serializer import serialize
from app.parsers.pdf_parser import parse_pdf_pages
from app.core.zone_classifier import classify_zones


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PDF_PATH = PROJECT_ROOT / "WEG-WMO.pdf"
PAGE_NUMBER = 5
DM_TITLE = "TERMINOLOGIE"
DM_TYPE = "descriptive"
OUTPUT_PATH = Path(__file__).resolve().parent / "terminalogie_page5.xml"


def _page_blocks(pdf_path: Path, page_number: int):
    pages = parse_pdf_pages(pdf_path)
    all_blocks = [block for page in pages for block in page.blocks]

    # La repetition des entetes/pieds ne peut etre detectee qu'en observant le
    # document complet, avant d'isoler la page du DM.
    classify_zones(all_blocks)
    return [
        block for block in all_blocks
        if block.page == page_number and block.zone == "body"
    ]


def generate_terminalogie_dm(
    pdf_path: Path = PDF_PATH,
    *,
    page_number: int = PAGE_NUMBER,
    dmc: str = "",
) -> tuple[str, list[dict]]:
    """Execute le parcours de generation pour le DM de terminologie."""
    guide = s1000d_guide.load_guide()
    descriptive_elements = {
        component
        for rule in guide.rules_for(DM_TYPE)
        for component in rule.components
    }
    required_elements = {"levelledPara", "title", "para", "randomList", "listItem", "note", "notePara"}
    missing_rules = required_elements - descriptive_elements
    if missing_rules:
        raise AssertionError(f"Regles descriptives absentes du guide : {sorted(missing_rules)}")

    blocks = _page_blocks(pdf_path, page_number)
    if not blocks:
        raise AssertionError(f"Aucun bloc exploitable sur la page {page_number}.")

    root = structure_infer.build_ir(blocks)
    context_classifier.apply_dm_type(root, DM_TYPE)
    resolve(root)

    xml = serialize(
        root,
        issue="4.2",
        dm_type=DM_TYPE,
        title=DM_TITLE,
        dm_metadata={
            "dmc": dmc,
            "tech_name": "Moteurs electriques",
            "info_name": DM_TITLE,
        },
    )
    violations = validator.validate_document(xml, issue="4.2")

    # Contrat minimal du premier DM descriptif.
    assert "<description>" in xml
    assert "<procedure>" not in xml
    assert "<title>TERMINOLOGIE</title>" in xml
    assert "<randomList>" in xml
    assert xml.count("<listItem>") == 2
    assert "<note>" in xml and "<notePara>" in xml
    assert xml.count('emphasisType="em01"') >= 6
    assert 'emphasisType="em02"' in xml
    assert "www.weg.net" not in xml
    assert "Manuel des Moteurs Électriques" not in xml
    assert "\x07" not in xml
    assert not any(v.get("rule") == "WELLFORMED" for v in violations)
    return xml, violations


def export_terminalogie_dm(xml: str, output_path: Path = OUTPUT_PATH) -> Path:
    """Ecrit le XML genere dans le dossier ``my_tests``."""
    output_path.write_text(xml, encoding="utf-8")
    return output_path


def main() -> int:
    xml, violations = generate_terminalogie_dm()
    output_path = export_terminalogie_dm(xml)
    print(xml)
    print(f"XML exporte dans : {output_path}", file=sys.stderr)
    if violations:
        print("\n<!-- Validation non bloquante -->", file=sys.stderr)
        for violation in violations:
            print(
                f"{violation.get('severity', 'info')}: "
                f"{violation.get('rule', '')}: {violation.get('message', '')}",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())