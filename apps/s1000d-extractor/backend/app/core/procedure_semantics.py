"""Source structure and resource fields shared by procedural review and XML."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from app.core.ir import IRNode
from app.core.preliminary_rule_defaults import HEADINGS

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
_CATEGORY_HEADINGS = {category: set(fr + en) for category, (fr, en) in HEADINGS.items()}
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
_TABLE_ANCHOR_EXCLUDED = {
    "equipment", "object", "removal and installation", "installation and removal",
}
_PERSONNEL_TABLE_ANCHORS = {
    "required person", "required persons", "required person s", "required personnel",
    "personnel required", "manpower",
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


def heading_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", normalize(heading_text(text))).strip()


def heading_scope(text: str, *, headings: dict[str, set[str]] | None = None) -> tuple[str, str | None]:
    label = heading_label(text)
    for phase, pattern in _PHASE_HEADINGS.items():
        if re.fullmatch(pattern, label):
            return phase, None
    for category, labels in (_CATEGORY_HEADINGS if headings is None else headings).items():
        if label in labels:
            return "preliminary", category
    return "unknown", None


def table_anchor_key(text: str) -> str:
    return heading_label(text)


def table_anchor_category(
    text: str, *, headings: dict[str, set[str]] | None = None,
) -> str | None:
    label = table_anchor_key(text)
    if not label or label in _TABLE_ANCHOR_EXCLUDED:
        return None
    if label in _PERSONNEL_TABLE_ANCHORS:
        return "personnel"
    phase, category = heading_scope(text, headings=headings)
    return category if phase == "preliminary" else None


def is_main_container(text: str) -> bool:
    return normalize(heading_text(text)).strip(" :") in {
        "main procedure", "mainprocedure", "procedure principale",
    }


def column_key(text: str) -> str | None:
    label = re.sub(r"[^a-z0-9]+", " ", normalize(text)).strip()
    return next((key for key, labels in _COLUMNS.items() if label in labels), None)


def table_heading(node: dict, *, headings: dict[str, set[str]] | None = None) -> list[str]:
    if node.get("table_header"):
        return node["table_header"]
    rows = node.get("table_rows") or []
    if rows:
        first_row = rows[0]
        if any(table_anchor_category(cell, headings=headings) for cell in first_row):
            return first_row
        keys = [
            column_key(cell) or (
                "name" if heading_scope(cell, headings=headings)[1] in {"personnel", "support", "supplies", "spares"}
                else None
            )
            for cell in rows[0]
        ]
        if "name" in keys and (len(rows[0]) == 1 or sum(key is not None for key in keys) >= 2):
            return rows[0]
    return []


def table_category(header: list[str], *, headings: dict[str, set[str]] | None = None) -> str | None:
    for cell in header:
        phase, category = heading_scope(cell, headings=headings)
        if phase == "preliminary" and category in {"personnel", "support", "supplies", "spares"}:
            return category
    return None


def passage_role(
    node: dict, row: int | None, text: str, *, headings: dict[str, set[str]] | None = None,
) -> str:
    if node.get("zone") in LAYOUT_ZONES:
        return "layout"
    if node["kind"] in {"section", "title"}:
        return "heading"
    if node["kind"] == "figure":
        return "caption"
    if row is not None and row == 0 and table_heading(node, headings=headings) == (node.get("table_rows") or [[]])[0]:
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
    target_tag: str | None = None


def resource_rows(sections: Sequence[IRNode]) -> list[Resource]:
    result = []
    for section in sections:
        for node in section.walk()[1:]:
            target_tag = node.candidates[0].element if node.candidates else None
            if node.kind in {"paragraph", "item"} and node.text.strip():
                result.append(Resource(
                    text=node.text.strip(), name=node.text.strip(), target_tag=target_tag,
                ))
            elif node.kind == "table":
                header = table_heading({"table_header": node.table_header, "table_rows": node.table_rows})
                for row_index, row in enumerate(node.table_rows or []):
                    if row == header:
                        continue
                    fields: dict[str, str] = {}
                    priorities: dict[str, int] = {}
                    remarks = []
                    cell_tags = (
                        node.reviewed_table_cell_tags[row_index]
                        if node.reviewed_table_cell_tags
                                               and row_index < len(node.reviewed_table_cell_tags)
                        else []
                    )
                    person_tag = None
                    person_tag_priority = 0
                    no_requirement_tag = None
                    for index, value in enumerate(row):
                        if not value.strip():
                            continue
                        label = header[index] if index < len(header) else ""
                        selected_tag = cell_tags[index] if index < len(cell_tags) else None
                        header_key = column_key(label)
                        tag_key = {
                            "name": "name",
                            "partNumber": "part_number",
                            "partAndSerialNumber": "part_number",
                            "manufacturerCode": "manufacturer",
                            "reqQuantity": "quantity",
                        }.get(selected_tag)
                        if selected_tag == "identNumber":
                            tag_key = header_key or "manufacturer"
                        key = tag_key or header_key
                        if selected_tag in {"personnel", "personCategory", "personSkill"}:
                            priority = 2 if selected_tag != "personnel" else 1
                            if priority > person_tag_priority:
                                person_tag = selected_tag
                                person_tag_priority = priority
                        if selected_tag in {"noSupportEquips", "noSupplies", "noSpares"}:
                            no_requirement_tag = selected_tag
                        if key:
                            priority = 2 if tag_key else 1
                            if priority > priorities.get(key, 0):
                                fields[key] = value.strip()
                                priorities[key] = priority
                        elif header:
                            remarks.append(f"{label}: {value}".strip(": "))
                    text = " ".join(cell.strip() for cell in row if cell.strip())
                    result.append(Resource(text=text, name=fields.get("name", text),
                                           quantity=fields.get("quantity"), unit=fields.get("unit"),
                                           part_number=fields.get("part_number"),
                                           manufacturer=fields.get("manufacturer"),
                                           remarks="; ".join(remarks) or None,
                                           target_tag=person_tag or no_requirement_tag or target_tag))
    return result
