"""Local, explainable proposals with lossless anchors into the source IR."""

from __future__ import annotations

import re
import unicodedata

CATEGORIES = ("conditions", "personnel", "support", "supplies", "spares", "safety")
DESTINATIONS = (*CATEGORIES, "body", "discard")
RULE_VERSION = 1

_PATTERNS = {
    "conditions": r"\b(before|prior to|ensure|make sure|prerequisite|condition|avant|assurer|prealable|hors tension)\b",
    "personnel": r"\b(personnel|technician|technicians|operator|operators|mechanic|qualified|technicien|techniciens|operateur|operateurs|qualification)\b",
    "support": r"\b(tool|tools|equipment|wrench|spanner|screwdriver|outillage|outil|outils|equipement|cle|tournevis)\b",
    "supplies": r"\b(consumable|consumables|supply|supplies|lubricant|grease|solvent|adhesive|consommable|consommables|graisse|solvant|colle)\b",
    "spares": r"\b(spare|spares|replacement part|replacement parts|rechange|joint neuf|new seal|new gasket)\b",
    "safety": r"\b(warning|caution|danger|hazard|safety|protective|avertissement|attention|risque|securite|protection)\b",
}
_RULES = {category: re.compile(pattern) for category, pattern in _PATTERNS.items()}


def _normalize(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )


def suggestion(text: str, inherited: str | None) -> tuple[str, str]:
    matches = [category for category, rule in _RULES.items() if rule.search(_normalize(text))]
    if len(matches) > 1:
        return "review", "multiple"
    if matches:
        return matches[0], "keywords"
    if inherited:
        return inherited, "heading"
    return "body", "unmatched"


def passages(tree: dict, *, source_format: str, page_offset: int) -> list[dict]:
    result: list[dict] = []
    reading_page, page_size = 1, 0

    def visit(node: dict, inherited: str | None = None, *, root: bool = False) -> None:
        nonlocal reading_page, page_size
        kind = node["kind"]
        heading, _ = suggestion(node.get("text", ""), None)
        if kind == "section" and heading in CATEGORIES:
            inherited = heading
        rows = node.get("table_rows") or []
        texts = (
            [(index, " | ".join(row)) for index, row in enumerate(rows)]
            if kind == "table" else [(None, node.get("text", ""))]
        )
        for row, text in texts:
            if root or not text.strip():
                continue
            if source_format == "docx" and page_size and page_size + len(text) > 2400:
                reading_page += 1
                page_size = 0
            page_size += len(text)
            page = (
                (node.get("page") + page_offset if node.get("page") else None)
                if source_format == "pdf" else reading_page
            )
            category, rule = suggestion(text, inherited)
            result.append({
                "id": f"{node['id']}:{row if row is not None else 'text'}:0",
                "node_id": node["id"],
                "row": row,
                "start": 0,
                "end": len(text),
                "source_text": text,
                "text": text,
                "page": page,
                "kind": kind,
                "suggested": category,
                "rule": rule,
                "decision": None,
            })
        for child in node.get("children", []):
            visit(child, inherited)

    visit(tree, root=True)
    return result
