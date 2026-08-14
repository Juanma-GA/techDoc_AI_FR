"""Ressources client d'un document : DMRL, templates, CIR, regles BREX JSON.

Isole du `wizard` la lecture des ressources optionnelles attachees a un
document et leur application a un DM (template -> CIR -> regles client), pour
que `wizard.py` reste une machine d'etapes.

Aucune ressource n'est obligatoire : absente, l'etape est simplement sautee
(degradation gracieuse, jamais d'echec).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from app.core import brex_rules as brex_rules_mod
from app.core import cir as cir_mod
from app.core import dm_templates
from app.core.dmrl import DmrlEntry, entry_from_dict
from app.db.models import Document

log = logging.getLogger("s1000d_extractor.resources")


@dataclass
class Resources:
    templates: dict[str, dict]
    cir: dict[str, dict]
    brex_rules: dict


def dmrl_entries(doc: Document) -> list[DmrlEntry]:
    if not doc.dmrl_json:
        return []
    return [entry_from_dict(d) for d in json.loads(doc.dmrl_json)]


def save_dmrl(doc: Document, entries: list[DmrlEntry]) -> None:
    doc.dmrl_json = json.dumps([e.to_dict() for e in entries], ensure_ascii=False)


def load_resources(doc: Document) -> Resources:
    """Charge templates + CIR + regles client. Une ressource illisible est
    tracee et ignoree (elle ne doit pas bloquer une generation)."""
    templates = _safe(lambda: dm_templates.load_templates(), {}, "templates")
    cir = _safe(lambda: cir_mod.load_cir(doc.cir_path), {}, "cir") if doc.cir_path else {}
    rules = (
        _safe(lambda: brex_rules_mod.load_brex_rules(doc.brex_rules_path), {}, "brex_rules")
        if doc.brex_rules_path else {}
    )
    return Resources(templates=templates, cir=cir, brex_rules=rules)


def _safe(fn, default, label: str):
    try:
        return fn()
    except Exception as exc:
        log.warning("ressource %s ignoree : %s", label, exc)
        return default


def _tree_text(tree: dict | None) -> str:
    """Texte lineaire d'un arbre IR (ordre de lecture) : entree des templates."""
    if not tree:
        return ""
    lines: list[str] = []

    def walk(node: dict) -> None:
        text = (node.get("text") or "").strip()
        if text:
            marker = "- " if node.get("kind") == "item" else ""
            lines.append(f"{marker}{text}")
        for child in node.get("children") or []:
            walk(child)

    walk(tree)
    return "\n".join(lines)


def apply_resources(dm: dict, res: Resources, document_text: str = "") -> tuple[dict, list[dict]]:
    """Applique CIR -> template -> regles client a un DM.

    Le CIR passe en premier : les rubriques du template doivent voir le contenu
    resolu, pas les jetons `{{CIR:...}}`. Renvoie `(dm_enrichi, violations)` ; le
    DM d'entree n'est pas mute.
    """
    out = dict(dm)
    if res.cir:
        out = cir_mod.resolve_cir_references(out, res.cir)
    template = dm_templates.template_for(res.templates, out.get("dm_type", ""))
    if template:
        out = dm_templates.generate_dm(out, template, document_text or _tree_text(out.get("tree")))
    violations: list[dict] = []
    if res.brex_rules:
        violations = brex_rules_mod.validate_dm_against_brex(out, res.brex_rules)
    for key in out.get("cir_unresolved") or []:
        violations.append({
            "severity": "warning", "rule": "CIR",
            "message": f"Reference CIR introuvable : {key}", "path": "/",
        })
    for key in out.get("missing_fields") or []:
        violations.append({
            "severity": "warning", "rule": "TEMPLATE",
            "message": f"Rubrique obligatoire du template vide : {key}", "path": "/",
        })
    return out, violations


def pmc_xml(doc: Document) -> str:
    """PMC XML du document (depuis sa DMRL). Chaine vide si aucune DMRL."""
    entries = dmrl_entries(doc)
    if not entries:
        return ""
    from app.core.dmrl import generate_pmc

    return generate_pmc(entries, pm_title=Path(doc.filename).stem)


# --- etape "DMRL" du wizard (validation avant decoupage) ---------------------

def dmrl_report(doc: Document) -> list[dict]:
    """Rapport d'appariement de la DMRL sur le document parse."""
    entries = dmrl_entries(doc)
    if not entries or not doc.ir_json:
        return [{**e.to_dict(), "index": i, "matched": False, "page": None, "matched_text": ""}
                for i, e in enumerate(entries)]
    from app.core import ir as ir_mod
    from app.core import splitter

    return splitter.match_report(ir_mod.from_dict(json.loads(doc.ir_json)), entries)


def apply_dmrl_op(doc: Document, params: dict) -> None:
    """Edition de la DMRL avant decoupage : rename / set_type / exclude.

    `index` designe la ligne (ordre du fichier source). Une entree exclue est
    retiree de la DMRL du document, pas du fichier d'origine.
    """
    entries = dmrl_entries(doc)
    index = params.get("index")
    if not isinstance(index, int) or not 0 <= index < len(entries):
        return
    op = params.get("op")
    if op == "rename":
        title = (params.get("title") or "").strip()
        if title:
            entries[index].title = title
    elif op == "set_type":
        dm_type = params.get("dm_type")
        if dm_type in ("descriptive", "procedural", "ipd"):
            entries[index].dm_type = dm_type
    elif op == "exclude":
        entries.pop(index)
    save_dmrl(doc, entries)
