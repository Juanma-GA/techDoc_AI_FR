"""Regles client (BREX projet exprime en JSON) : validation d'un DM genere.

Complement du BREX XML S1000D (`core.brex`, qui valide le XML produit) : ici on
valide le DM *avant* serialisation, sur des criteres redactionnels que les
clients imposent souvent et qui ne sont pas exprimables en `structureObjectRule`
(profondeur de titres, longueur de titre, rubriques obligatoires, types de DM
autorises, profondeur de listes).

Format du fichier (JSON) :

    {
      "name": "Client X",
      "max_title_levels": 2,
      "max_title_length": 120,
      "allowed_dm_types": ["descriptive", "procedural"],
      "forbidden_kinds": ["table"],
      "required_sections": ["description"],
      "max_list_depth": 2
    }
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.errors import AppError

_KNOWN_KEYS = {
    "name", "max_title_levels", "max_title_length", "allowed_dm_types",
    "forbidden_kinds", "required_sections", "max_list_depth",
}


def load_brex_rules(file_path: str | Path) -> dict:
    """Charge les regles client (JSON). Erreur explicite si illisible."""
    path = Path(file_path)
    if not path.exists():
        raise AppError("BREX_RULES_NOT_FOUND", f"Regles BREX introuvables : {path.name}", 404)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AppError("BREX_RULES_INVALID", f"Regles BREX illisibles : {exc}", 422) from exc
    if not isinstance(data, dict):
        raise AppError("BREX_RULES_INVALID", "Regles BREX invalides (objet JSON attendu).", 422)
    unknown = sorted(set(data) - _KNOWN_KEYS)
    if unknown:
        # Signale sans bloquer : une regle inconnue ne doit pas passer inapercue.
        data = {**data, "_unknown_keys": unknown}
    return data


def _v(rule: str, message: str, path: str = "/", severity: str = "error") -> dict:
    return {"severity": severity, "rule": rule, "message": message, "path": path}


def _walk(node: dict, depth: int, out: list[tuple[dict, int]]) -> None:
    out.append((node, depth))
    child_depth = depth + 1 if node.get("kind") == "section" else depth
    for child in node.get("children") or []:
        _walk(child, child_depth, out)


def _list_depth(node: dict, current: int = 0) -> int:
    depth = current + 1 if node.get("kind") == "item-sequence" else current
    depths = [depth]
    for child in node.get("children") or []:
        depths.append(_list_depth(child, depth))
    return max(depths)


def validate_dm_against_brex(dm: dict, brex_rules: dict) -> list[dict]:
    """Confronte un DM (dict wizard : title / dm_type / tree / sections) aux
    regles client. Renvoie une liste de violations au format unifie."""
    if not brex_rules:
        return []
    out: list[dict] = []
    tree = dm.get("tree") or {}
    nodes: list[tuple[dict, int]] = []
    if tree:
        _walk(tree, 0, nodes)

    allowed = brex_rules.get("allowed_dm_types")
    if allowed and dm.get("dm_type") not in allowed:
        out.append(_v("BREX_DM_TYPE", f"Type de DM non autorise : {dm.get('dm_type')}"))

    max_levels = brex_rules.get("max_title_levels")
    if isinstance(max_levels, int):
        for node, depth in nodes:
            if node.get("kind") == "section" and depth > max_levels:
                out.append(_v(
                    "BREX_TITLE_LEVEL",
                    f"Niveau de titre {depth} > maximum autorise ({max_levels}) : "
                    f"{node.get('text') or ''}",
                    node.get("id", "/"),
                ))

    max_len = brex_rules.get("max_title_length")
    if isinstance(max_len, int):
        titles = [dm.get("title") or ""] + [
            n.get("text") or "" for n, _ in nodes if n.get("kind") == "section"
        ]
        for title in titles:
            if len(title) > max_len:
                out.append(_v("BREX_TITLE_LENGTH", f"Titre trop long ({len(title)} > {max_len})."))

    forbidden = set(brex_rules.get("forbidden_kinds") or [])
    if forbidden:
        for node, _ in nodes:
            if node.get("kind") in forbidden:
                out.append(_v(
                    "BREX_FORBIDDEN", f"Element interdit par le client : {node.get('kind')}",
                    node.get("id", "/"),
                ))

    required = brex_rules.get("required_sections") or []
    if required:
        filled = {
            s.get("key") for s in (dm.get("sections") or [])
            if isinstance(s, dict) and str(s.get("content") or "").strip()
        }
        for key in required:
            if key not in filled:
                out.append(_v("BREX_REQUIRED_SECTION", f"Rubrique obligatoire vide ou absente : {key}"))

    max_list = brex_rules.get("max_list_depth")
    if isinstance(max_list, int) and tree and _list_depth(tree) > max_list:
        out.append(_v("BREX_LIST_DEPTH", f"Imbrication de listes > maximum autorise ({max_list})."))

    for key in brex_rules.get("_unknown_keys") or []:
        out.append(_v("BREX_UNKNOWN_RULE", f"Regle client inconnue, ignoree : {key}", "/", "info"))
    return out
