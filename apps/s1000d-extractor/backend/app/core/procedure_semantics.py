"""Source structure and resource fields shared by procedural review and XML."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.ir import IRNode

REQUIREMENT_CATEGORIES = ("conditions", "personnel", "support", "supplies", "spares", "safety")
EXTRA_DESTINATIONS = ("common", "closing")
LAYOUT_ZONES = frozenset({"header", "footer", "cover", "toc"})
_NUMBERED_HEADING = re.compile(
    r"^\s*(?:(?:chapter|chapitre|section)\s+)?\d{1,3}(?:\.\d+)*(?:[.)]\s*|[-:]\s+|\s+)",
    re.IGNORECASE,
)
_TECHNICAL_UNIT = re.compile(
    r"^(?:v|kv|a|ma|hz|khz|mhz|bar|psi|pa|n|nm|mm|cm|m|kg|g|ml|l|c)\b",
    re.IGNORECASE,
)
_MARKER = re.compile(r"^(?:(?:chapter|chapitre|section)\s+)?\d+(?:\.\d+)+\.?$")
_CATEGORY_HEADINGS = {
    "conditions": r"(?:preconditions?|prerequisites?|required conditions?|conditions?(?: prealables?| requises?| a respecter)?)",
    "personnel": r"(?:(?:required |qualified )?personnel(?: requis| necessaire)?|manpower)",
    "support": r"(?:(?:required |special )?(?:support equipment|tools?|tooling|equipment|outillage|outils?|equipements?)(?: required| necessaires?| requis)?)",
    "supplies": r"(?:required )?(?:supplies|consumables?|fournitures?|consommables?)(?: required| requis)?",
    "spares": r"(?:required )?(?:spares?|spare parts|pieces? (?:de )?rechange)(?: required| requises?)?",
    "safety": r"(?:(?:general |required )?safety(?: requirements?| precautions?)?|security requirements?|securite|precautions?(?: de securite)?)",
}
_PHASE_HEADINGS = {
    "preliminary": r"(?:preliminary (?:requirements|requisites)|exigences preliminaires|preliminaires|prerequis)",
    "main": r"(?:main procedure|procedure(?: principale)?|procedure steps|instructions?|operations?|removal|installation|depose|repose|demontage|montage|inspection|repair|reparation)",
    "closing": r"(?:closing requirements|close ?up(?: requirements)?|final conditions|conditions? finales?|exigences? (?:finales?|de cloture)|remise en etat(?: apres intervention)?)",
    "common": r"(?:common (?:information|info)|general (?:information|description)|generalites|informations generales)",
}
_ACTION = re.compile(
    r"^(?:use|install|remove|disconnect|connect|tighten|loosen|apply|inspect|check|"
    r"replace|clean|open|close|attach|detach|measure|utiliser|installer|deposer|"
    r"retirer|debrancher|brancher|raccorder|serrer|desserrer|appliquer|verifier|"
    r"remplacer|nettoyer|ouvrir|fermer|mesurer)\b"
)
_COLUMNS = {
    "name": {"name", "description", "designation", "tool", "tools", "equipment", "outil", "outillage",
             "consumable", "consumables", "consommable", "spare", "spares", "piece", "trade", "metier", "personnel"},
    "quantity": {"qty", "quantity", "quantite", "qte", "number required", "num required", "nombre"},
    "unit": {"unit", "units", "unit of measure", "uom", "unite", "unites"},
    "part_number": {"part number", "part no", "partnumber", "pn", "p n", "reference", "ref"},
    "manufacturer": {"manufacturer", "manufacturer code", "cage", "cage code", "code fabricant", "fabricant"},
}


def normalize(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )


def heading_text(text: str) -> str:
    if re.fullmatch(r"(?:(?:chapter|chapitre|section)\s+)?\d+(?:\.\d+)*[.)]?", normalize(text.strip())):
        return ""
    stripped = _NUMBERED_HEADING.sub("", text, count=1)
    if stripped != text and _TECHNICAL_UNIT.match(stripped):
        return text.strip()
    return stripped.strip()


def heading_scope(text: str) -> tuple[str, str | None]:
    label = re.sub(r"[^a-z0-9]+", " ", normalize(heading_text(text))).strip()
    for phase, pattern in _PHASE_HEADINGS.items():
        if re.fullmatch(pattern, label):
            return phase, None
    for category, pattern in _CATEGORY_HEADINGS.items():
        if re.fullmatch(pattern, label):
            return "preliminary", category
    return "unknown", None


def is_main_container(text: str) -> bool:
    return normalize(heading_text(text)).strip(" :") in {
        "main procedure", "mainprocedure", "procedure principale",
    }


def column_key(text: str) -> str | None:
    label = re.sub(r"[^a-z0-9]+", " ", normalize(text)).strip()
    return next((key for key, labels in _COLUMNS.items() if label in labels), None)


def table_heading(node: dict) -> list[str]:
    if node.get("table_header"):
        return node["table_header"]
    rows = node.get("table_rows") or []
    if rows:
        keys = [column_key(cell) for cell in rows[0]]
        if "name" in keys and (len(rows[0]) == 1 or sum(key is not None for key in keys) >= 2):
            return rows[0]
    return []


def table_category(header: list[str]) -> str | None:
    for cell in header:
        phase, category = heading_scope(cell)
        if phase == "preliminary" and category in {"personnel", "support", "supplies", "spares"}:
            return category
    return None


def passage_role(node: dict, row: int | None, text: str) -> str:
    if node.get("zone") in LAYOUT_ZONES:
        return "layout"
    if node["kind"] in {"section", "title"}:
        return "heading"
    if node["kind"] == "figure":
        return "caption"
    if row is not None and row == 0 and table_heading(node) == (node.get("table_rows") or [[]])[0]:
        return "table-header"
    if node["kind"] == "paragraph" and node.get("zone") == "chapter" and (
        _MARKER.fullmatch(normalize(text.strip()))
        or re.fullmatch(r"\d+[.)]?", text.strip())
    ):
        return "marker"
    return "content"


def is_action(text: str) -> bool:
    return bool(_ACTION.match(normalize(heading_text(text))))


@dataclass(frozen=True)
class Resource:
    text: str
    name: str
    quantity: str | None = None
    unit: str | None = None
    part_number: str | None = None
    manufacturer: str | None = None
    remarks: str | None = None


def resource_rows(sections: Sequence[IRNode]) -> list[Resource]:
    result = []
    for section in sections:
        for node in section.walk()[1:]:
            if node.kind in {"paragraph", "item"} and node.text.strip():
                result.append(Resource(text=node.text.strip(), name=node.text.strip()))
            elif node.kind == "table":
                header = table_heading({"table_header": node.table_header, "table_rows": node.table_rows})
                for row in node.table_rows or []:
                    if row == header:
                        continue
                    fields: dict[str, str] = {}
                    remarks = []
                    for index, value in enumerate(row):
                        if not value.strip():
                            continue
                        label = header[index] if index < len(header) else ""
                        key = column_key(label)
                        if key and key not in fields:
                            fields[key] = value.strip()
                        elif header:
                            remarks.append(f"{label}: {value}".strip(": "))
                    text = " | ".join(row)
                    result.append(Resource(text=text, name=fields.get("name", text),
                                           quantity=fields.get("quantity"), unit=fields.get("unit"),
                                           part_number=fields.get("part_number"),
                                           manufacturer=fields.get("manufacturer"),
                                           remarks="; ".join(remarks) or None))
    return result
