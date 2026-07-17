"""Assistant guide (wizard) : configuration etape par etape d'une migration.

Etapes bloquantes, l'utilisateur valide chacune avant la suivante :

    split     -> decoupage en Data Modules (choix du niveau)
    type      -> type de chaque DM (descriptive / procedural / ipd)
    structure -> arbre par DM + arbitrage des noeuds ambigus
    generate  -> XML S1000D par DM + validation

L'etat vit sur le `Document` : `wizard_step`, `split_level`, `ir_json` (IR
complet apres parse) et `dms_json` (liste de DM en cours de configuration).
Chaque DM : {dm_id, title, dm_type, tree, xml?, violations?}.

Ce module tient la machine d'etapes ; l'edition du decoupage (rename / exclude /
merge / split / masquage entetes-pieds / undo / apercu) vit dans `wizard_split`.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.core import context_classifier, ingest, resolver, splitter, structure_infer
from app.core import ir as ir_mod
from app.core import wizard_split as ws
from app.core.errors import AppError
from app.core.s1000d_serializer import serialize
from app.core.validator import validate_document
from app.db.models import BrexProfile, Document

STEPS = ("split", "type", "structure", "generate")
_DEFAULT_LEVEL = "section"


# --- helpers d'etat ----------------------------------------------------------

def _brex_xml(db: Session, brex_id: str | None) -> str | None:
    if not brex_id:
        return None
    b = db.get(BrexProfile, brex_id)
    if b and Path(b.xml_path).exists():
        return Path(b.xml_path).read_text(encoding="utf-8")
    return None


def images_dir(doc_id: str) -> Path:
    """Dossier des illustrations extraites d'un document."""
    from app.config import settings
    return Path(settings.storage_dir) / f"document_{doc_id}_images"


def _extract_illustrations(doc: Document, root: ir_mod.IRNode) -> None:
    """Extrait les images du PDF en JPG et pose l'ICN sur les figures (no-op si
    echec / pas d'image)."""
    from app.core import illustrations
    try:
        illustrations.attach_illustrations(
            root, pdf_path=doc.storage_path, out_dir=images_dir(doc.id), doc_id=doc.id
        )
    except Exception:  # jamais bloquant : le squelette reste generable sans images
        pass


# --- transitions -------------------------------------------------------------

def _noop_progress(step: str, pct: int) -> None:
    pass


def start(db: Session, doc: Document, progress_cb=_noop_progress) -> dict:
    """Parse le document, construit l'IR, propose un decoupage par defaut.

    `progress_cb(step, pct)` permet de streamer la progression (parse / ocr /
    infer / split / classify) vers une barre cote UI.
    """
    progress_cb("parse", 10)
    blocks = ingest.extract_blocks(
        doc.storage_path, fmt=doc.source_format, db=db, progress_cb=progress_cb
    )
    progress_cb("infer", 40)
    root = structure_infer.build_ir(blocks)
    if doc.source_format == "pdf":
        _extract_illustrations(doc, root)
    doc.ir_json = json.dumps(ir_mod.to_dict(root), ensure_ascii=False)
    doc.split_level = _DEFAULT_LEVEL
    ws.reset_history(doc)                      # nouvel assistant -> pile undo vide
    _resplit(db, doc, _DEFAULT_LEVEL, progress_cb=progress_cb)
    doc.wizard_step = "split"
    doc.status = "wizard"
    progress_cb("done", 100)
    db.commit()
    return state(doc)


def _resplit(db: Session, doc: Document, split_level: str, progress_cb=_noop_progress) -> None:
    """Recoupe l'IR en DMs et propose un type pour chacun."""
    progress_cb("split", 60)
    root = ir_mod.from_dict(json.loads(doc.ir_json))
    units = splitter.split_into_dms(root, split_level)
    progress_cb("classify", 80)
    types = context_classifier.classify_dms(units, hint=doc.context_hint, db=db)
    ws.save_dms(doc, [
        {
            "dm_id": u.dm_id,
            "title": u.title,
            "dm_type": types[u.dm_id],
            "tree": ir_mod.to_dict(u.root),
            "xml": None,
            "violations": None,
        }
        for u in units
    ])
    doc.split_level = split_level


def update(db: Session, doc: Document, params: dict) -> dict:
    """Recalcule l'etape courante avec de nouveaux parametres (sans avancer).

    A l'etape split : `op` (edition manuelle / masquage / undo) ou `split_level`
    (re-analyse complete qui ecrase les ajustements). L'historique undo n'est
    empile qu'ICI, jamais dans `_resplit`/`apply_split_op` (partages avec
    `start`/`advance`)."""
    if doc.wizard_step == "split":
        op = params.get("op")
        if op == "undo":
            ws.undo(doc)
        else:
            ws.push_history(doc)
            if op == "hide_zones":
                ws.hide_zones(doc, params.get("zones") or ["header", "footer"])
            elif op:
                ws.apply_split_op(doc, params)
            else:
                _resplit(db, doc, params.get("split_level", doc.split_level))
        db.commit()
    return state(doc)


def advance(db: Session, doc: Document, params: dict) -> dict:
    step = doc.wizard_step
    if step == "split":
        # Ne re-decouper QUE si le niveau a explicitement change : sinon on
        # ecraserait les editions manuelles (exclure / fusionner / scinder /
        # renommer). Le decoupage valide doit etre respecte a l'etape suivante.
        new_level = params.get("split_level")
        if new_level and new_level != doc.split_level:
            _resplit(db, doc, new_level)
        doc.wizard_step = "type"
    elif step == "type":
        _apply_types(doc, params.get("types") or {})
        _resolve_all(doc)
        doc.wizard_step = "structure"
    elif step == "structure":
        _apply_overrides(doc, params.get("overrides") or [])
        _generate_all(db, doc)
        doc.wizard_step = "generate"
        doc.status = "extracted"
    elif step == "generate":
        return state(doc)
    db.commit()
    return state(doc)


def back(db: Session, doc: Document) -> dict:
    idx = STEPS.index(doc.wizard_step) if doc.wizard_step in STEPS else 0
    doc.wizard_step = STEPS[max(0, idx - 1)]
    db.commit()
    return state(doc)


def _apply_types(doc: Document, types: dict) -> None:
    dms = ws.load_dms(doc)
    for dm in dms:
        if dm["dm_id"] in types and types[dm["dm_id"]] in context_classifier.DM_TYPES:
            dm["dm_type"] = types[dm["dm_id"]]
    ws.save_dms(doc, dms)


def _resolve_all(doc: Document) -> None:
    dms = ws.load_dms(doc)
    for dm in dms:
        root = ir_mod.from_dict(dm["tree"])
        resolver.resolve(root)
        dm["tree"] = ir_mod.to_dict(root)
    ws.save_dms(doc, dms)


def _apply_overrides(doc: Document, overrides: list[dict]) -> None:
    dms = ws.load_dms(doc)
    by_id = {dm["dm_id"]: ir_mod.from_dict(dm["tree"]) for dm in dms}
    for ov in overrides:
        root = by_id.get(ov.get("dm_id"))
        if root is None:
            continue
        node = ir_mod.find_node(root, ov.get("node_id", ""))
        if node is None:
            continue
        chosen = ir_mod.Candidate(ov["element"], 1.0, "Choix humain")
        node.candidates = [chosen] + [c for c in node.candidates if c.element != ov["element"]]
        node.confidence = 1.0
    for dm in dms:
        dm["tree"] = ir_mod.to_dict(by_id[dm["dm_id"]])
    ws.save_dms(doc, dms)


def _generate_all(db: Session, doc: Document) -> None:
    dms = ws.load_dms(doc)
    brex_xml = _brex_xml(db, doc.brex_id)
    for dm in dms:
        root = ir_mod.from_dict(dm["tree"])
        xml = serialize(root, issue=doc.s1000d_issue, dm_type=dm["dm_type"], title=dm["title"])
        dm["xml"] = xml
        dm["violations"] = validate_document(xml, issue=doc.s1000d_issue, brex_xml=brex_xml)
    ws.save_dms(doc, dms)


# --- vue d'etat --------------------------------------------------------------

def state(doc: Document) -> dict:
    dms = ws.load_dms(doc)
    step = doc.wizard_step or "split"
    out_dms = []
    for dm in dms:
        entry = {
            "dm_id": dm["dm_id"],
            "title": dm["title"],
            "dm_type": dm["dm_type"],
            "node_count": ws.node_count(dm["tree"]),
        }
        if step == "split":
            entry["preview"] = ws.dm_preview(dm["tree"])
        if step == "structure":
            entry["tree"] = dm["tree"]
        if step == "generate":
            entry["violation_count"] = len(dm.get("violations") or [])
            entry["has_xml"] = bool(dm.get("xml"))
        out_dms.append(entry)
    return {
        "step": step,
        "split_level": doc.split_level or _DEFAULT_LEVEL,
        "steps": list(STEPS),
        "can_undo": step == "split" and ws.can_undo(doc),
        "dms": out_dms,
    }


def dm_xml(doc: Document, dm_id: str) -> str:
    for dm in ws.load_dms(doc):
        if dm["dm_id"] == dm_id:
            if not dm.get("xml"):
                raise AppError("NO_XML", "XML non genere : termine l'etape Generation.", 409)
            return dm["xml"]
    raise AppError("DM_NOT_FOUND", f"DM inconnu : {dm_id}", 404)
