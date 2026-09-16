"""Generation manuelle d'un seul Data Module depuis une page PDF.

Exemples depuis la racine du projet :

    .venv\\Scripts\\python.exe backend\\tests\\my_tests\\test_xml_byhand.py \
        --page 5 --title TERMINOLOGIE --type descriptive

    .venv\\Scripts\\python.exe backend\\tests\\my_tests\\test_xml_byhand.py \
        --page 6 --title "RECOMMANDATIONS INITIALES" --type proced

Le script applique les phases utiles du pipeline : extraction, detection des
zones, construction IR, choix manuel du type, segmentation des actions,
resolution, serialisation et validation non bloquante. Le XML est imprime et
exporte dans ``backend/tests/my_tests`` par defaut.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import unicodedata

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core import context_classifier, form_segmenter, s1000d_guide, structure_infer
from app.core import validator
from app.core.resolver import resolve
from app.core.s1000d_serializer import serialize
from app.core.zone_classifier import classify_zones
from app.parsers.pdf_parser import parse_pdf_pages


PROJECT_ROOT = BACKEND_ROOT.parent
OUTPUT_DIRECTORY = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Configuration manuelle : modifiez ces valeurs puis lancez le fichier sans
# argument. Les options de ligne de commande restent disponibles et prioritaires.
# ---------------------------------------------------------------------------
PDF_PATH = PROJECT_ROOT / "WEG-WMO.pdf"
PAGE_NUMBER = 5
DM_TITLE = "TERMINOLOGIE"
DM_TYPE = "descriptive"  # "descriptive" ou "procedural"
ISSUE = "4.2"
DMC = ""  # Laissez vide si le DMC n'est pas encore connu.
TECH_NAME = "Moteurs electriques"
INFO_NAME = "Terminologie"
OUTPUT_PATH: Path | None = OUTPUT_DIRECTORY / "terminologie.xml"  # Ou OUTPUT_DIRECTORY / "mon_dm.xml"

_TYPE_ALIASES = {
    "descriptive": "descriptive",
    "descriptif": "descriptive",
    "description": "descriptive",
    "procedural": "procedural",
    "procedure": "procedural",
    "proced": "procedural",
}


def normalize_dm_type(value: str) -> str:
    """Convertit le choix manuel en type interne accepte par le pipeline."""
    normalized = (value or "").strip().casefold()
    try:
        return _TYPE_ALIASES[normalized]
    except KeyError as exc:
        choices = ", ".join(sorted({"descriptive", "descriptif", "procedural", "proced"}))
        raise ValueError(f"Type de DM inconnu : {value!r}. Choix : {choices}.") from exc


def _slug(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value or "")
    ascii_value = "".join(char for char in folded if not unicodedata.combining(char))
    result = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_value).strip("_").lower()
    return result or "dm"


def default_output_path(title: str, page_number: int) -> Path:
    return OUTPUT_DIRECTORY / f"{_slug(title)}_page{page_number}.xml"


def _page_blocks(pdf_path: Path, page_number: int):
    pages = parse_pdf_pages(pdf_path)
    if page_number < 1 or page_number > len(pages):
        raise ValueError(f"Page hors limites : {page_number} (PDF : 1-{len(pages)}).")

    all_blocks = [block for page in pages for block in page.blocks]
    # Les repetitions ne sont visibles qu'en observant toutes les pages.
    classify_zones(all_blocks)
    blocks = [
        block for block in all_blocks
        if block.page == page_number and block.zone == "body"
    ]
    if not blocks:
        raise ValueError(f"Aucun bloc exploitable sur la page {page_number}.")
    return blocks


def _guide_warnings(dm_type: str) -> list[dict]:
    guide = s1000d_guide.load_guide()
    rules = guide.rules_for(dm_type)
    if not rules:
        raise ValueError(f"Le guide ne contient aucune regle pour le profil {dm_type}.")

    elements = {component for rule in rules for component in rule.components}
    expected = {"title", "para"}
    if dm_type == "descriptive":
        expected.update({"levelledPara", "randomList", "listItem"})
    else:
        expected.update({"proceduralStep", "preliminaryRqmts"})
    return [
        {
            "severity": "warning",
            "rule": "GUIDE_PROFILE",
            "message": f"Balise attendue absente du profil {dm_type} : {element}.",
            "path": "/",
        }
        for element in sorted(expected - elements)
    ]


def generate_dm(
    pdf_path: Path = PDF_PATH,
    *,
    page_number: int = PAGE_NUMBER,
    title: str = DM_TITLE,
    dm_type: str = DM_TYPE,
    issue: str = ISSUE,
    dmc: str = DMC,
    tech_name: str = TECH_NAME,
    info_name: str = INFO_NAME,
) -> tuple[str, list[dict]]:
    """Genere un seul DM a partir de la page choisie."""
    normalized_type = normalize_dm_type(dm_type)
    violations = _guide_warnings(normalized_type)
    blocks = _page_blocks(pdf_path, page_number)

    root = structure_infer.build_ir(blocks)
    # Le type fourni par l'utilisateur est la decision metier autoritaire.
    context_classifier.apply_dm_type(root, normalized_type)
    if normalized_type == "procedural":
        form_segmenter.segment(root)
    resolve(root)

    xml = serialize(
        root,
        issue=issue,
        dm_type=normalized_type,
        title=title,
        dm_metadata={
            "dmc": dmc,
            "tech_name": tech_name or title,
            "info_name": info_name or title,
        },
    )
    violations.extend(validator.validate_document(xml, issue=issue))
    if any(violation.get("rule") == "WELLFORMED" for violation in violations):
        raise ValueError("Le XML genere n'est pas bien forme.")
    return xml, violations


def export_xml(xml: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(xml, encoding="utf-8")
    return output_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Genere un seul DM XML depuis une page PDF.")
    parser.add_argument("--pdf", type=Path, default=PDF_PATH, help="PDF source.")
    parser.add_argument("--page", type=int, default=PAGE_NUMBER, help="Numero de page physique.")
    parser.add_argument("--title", default=DM_TITLE, help="Titre du DM.")
    parser.add_argument(
        "--type",
        dest="dm_type",
        default=DM_TYPE,
        help="Type manuel : descriptive/descriptif ou procedural/proced.",
    )
    parser.add_argument("--issue", default=ISSUE, help="Issue S1000D, par exemple 4.2.")
    parser.add_argument("--dmc", default=DMC, help="DMC complet si connu.")
    parser.add_argument("--tech-name", default=TECH_NAME, help="TechName du DM.")
    parser.add_argument("--info-name", default=INFO_NAME, help="InfoName du DM.")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Fichier XML de sortie; sinon OUTPUT_PATH puis nom automatique.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    xml, violations = generate_dm(
        args.pdf,
        page_number=args.page,
        title=args.title,
        dm_type=args.dm_type,
        issue=args.issue,
        dmc=args.dmc,
        tech_name=args.tech_name,
        info_name=args.info_name,
    )
    output_path = args.output or OUTPUT_PATH or default_output_path(args.title, args.page)
    export_xml(xml, output_path)
    print(xml)
    print(f"XML exporte dans : {output_path}", file=sys.stderr)
    for violation in violations:
        print(
            f"{violation.get('severity', 'info')}: "
            f"{violation.get('rule', '')}: {violation.get('message', '')}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())