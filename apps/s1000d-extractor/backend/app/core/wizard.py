"""Assistant guide (wizard) : configuration etape par etape d'une migration.

Etapes bloquantes, l'utilisateur valide chacune avant la suivante :

    split     -> decoupage en Data Modules (choix du niveau)
    type      -> type de chaque DM (descriptive / procedural / ipd)
    structure -> arbre par DM + arbitrage des noeuds ambigus
    generate  -> XML S1000D par DM + validation

L'etat vit sur le `Document` : `wizard_step`, `split_level`, `ir_json` (IR
complet apres parse) et `dms_json` (liste de DM en cours de configuration).
Chaque DM : {dm_id, title, dm_type, tree, xml?, violations?}.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core import context_classifier, ingest, resolver, splitter, structure_infer
from app.core import ir as ir_mod
from app.core.errors import AppError
from app.core.s1000d_serializer import serialize
from app.core.validator import validate_document
from app.db.models import BrexProfile, Document

STEPS = ("split", "type", "structure", "generate")
_DEFAULT_LEVEL = "section"


# --- helpers d'etat ----------------------------------------------------------

def _load_dms(doc: Document) -> list[dict]:
    return json.loads(doc.dms_json) if doc.dms_json else []


def _save_dms(doc: Document, dms: list[dict]) -> None:
    doc.dms_json = json.dumps(dms, ensure_ascii=False)


def _node_count(tree: dict) -> int:
    return 1 + sum(_node_count(c) for c in tree.get("children", []))


def _brex_xml(db: Session, brex_id: str | None) -> str | None:
    from pathlib import Path
    if not brex_id:
        return None
    b = db.get(BrexProfile, brex_id)
    if b and Path(b.xml_path).exists():
        return Path(b.xml_path).read_text(encoding="utf-8")
    return None


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
    doc.ir_json = json.dumps(ir_mod.to_dict(root), ensure_ascii=False)
    doc.split_level = _DEFAULT_LEVEL
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
    _save_dms(doc, [
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

    A l'etape split : soit `op` (edition manuelle : exclude / merge / split /
    rename), soit `split_level` (re-analyse complete qui ecrase les ajustements).
    """
    if doc.wizard_step == "split":
        if params.get("op"):
            _apply_split_op(doc, params)
        else:
            _resplit(db, doc, params.get("split_level", doc.split_level))
        db.commit()
    return state(doc)


def _renumber(dms: list[dict]) -> list[dict]:
    for i, d in enumerate(dms, start=1):
        d["dm_id"] = f"dm{i}"
    return dms


def _retype(dm: dict) -> str:
    root = ir_mod.from_dict(dm["tree"])
    return context_classifier.guess_dm_type(dm["title"], root)


def _split_one(dm: dict) -> list[dict]:
    """Scinde un DM en sous-DMs (1 par section enfant). Renvoie [dm] si on ne
    peut pas le scinder (aucune section enfant)."""
    root = ir_mod.from_dict(dm["tree"])
    units: list[list] = []
    lead: list = []
    for child in root.children:
        if child.kind == "section":
            syn = ir_mod.IRNode(id="x", kind="section", level=0, children=list(child.children))
            units.append([child.text or "Section", syn])
        elif units:
            units[-1][1].children.append(child)
        else:
            lead.append(child)
    parts: list[tuple] = []
    if lead:
        lead_root = ir_mod.IRNode(id="x", kind="section", level=0, children=lead)
        parts.append((f"{dm['title']} (general)", lead_root))
    parts.extend((t, s) for t, s in units)
    if len(parts) < 2:
        return [dm]
    return [
        {"dm_id": "tmp", "title": t, "dm_type": context_classifier.guess_dm_type(t, s),
         "tree": ir_mod.to_dict(s), "xml": None, "violations": None}
        for t, s in parts
    ]


def _apply_split_op(doc: Document, params: dict) -> None:
    op = params["op"]
    dms = _load_dms(doc)
    if op == "rename":
        title = (params.get("title") or "").strip()
        for d in dms:
            if d["dm_id"] == params.get("id") and title:
                d["title"] = title
    elif op == "exclude":
        dms = _renumber([d for d in dms if d["dm_id"] != params.get("id")])
    elif op == "merge":
        ids = params.get("ids") or []
        sel = [d for d in dms if d["dm_id"] in ids]
        if len(sel) >= 2:
            first = sel[0]
            children: list = []
            for d in sel:
                children.extend(d["tree"].get("children", []))
            first["tree"]["children"] = children
            first["dm_type"] = _retype(first)
            dms = _renumber([d for d in dms if d["dm_id"] == first["dm_id"] or d["dm_id"] not in ids])
    elif op == "split":
        target = next((d for d in dms if d["dm_id"] == params.get("id")), None)
        if target:
            subs = _split_one(target)
            if len(subs) >= 2:
                pos = dms.index(target)
                dms = _renumber(dms[:pos] + subs + dms[pos + 1:])
    _save_dms(doc, dms)


def advance(db: Session, doc: Document, params: dict) -> dict:
    step = doc.wizard_step
    if step == "split":
        if params.get("split_level"):
            _resplit(db, doc, params["split_level"])
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
    dms = _load_dms(doc)
    for dm in dms:
        if dm["dm_id"] in types and types[dm["dm_id"]] in context_classifier.DM_TYPES:
            dm["dm_type"] = types[dm["dm_id"]]
    _save_dms(doc, dms)


def _resolve_all(doc: Document) -> None:
    dms = _load_dms(doc)
    for dm in dms:
        root = ir_mod.from_dict(dm["tree"])
        resolver.resolve(root)
        dm["tree"] = ir_mod.to_dict(root)
    _save_dms(doc, dms)


def _apply_overrides(doc: Document, overrides: list[dict]) -> None:
    dms = _load_dms(doc)
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
    _save_dms(doc, dms)


def _generate_all(db: Session, doc: Document) -> None:
    dms = _load_dms(doc)
    brex_xml = _brex_xml(db, doc.brex_id)
    for dm in dms:
        root = ir_mod.from_dict(dm["tree"])
        xml = serialize(root, issue=doc.s1000d_issue, dm_type=dm["dm_type"], title=dm["title"])
        dm["xml"] = xml
        dm["violations"] = validate_document(xml, issue=doc.s1000d_issue, brex_xml=brex_xml)
    _save_dms(doc, dms)


# --- vue d'etat --------------------------------------------------------------

def state(doc: Document) -> dict:
    dms = _load_dms(doc)
    step = doc.wizard_step or "split"
    out_dms = []
    for dm in dms:
        entry = {
            "dm_id": dm["dm_id"],
            "title": dm["title"],
            "dm_type": dm["dm_type"],
            "node_count": _node_count(dm["tree"]),
        }
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
        "dms": out_dms,
    }


def dm_xml(doc: Document, dm_id: str) -> str:
    for dm in _load_dms(doc):
        if dm["dm_id"] == dm_id:
            if not dm.get("xml"):
                raise AppError("NO_XML", "XML non genere : termine l'etape Generation.", 409)
            return dm["xml"]
    raise AppError("DM_NOT_FOUND", f"DM inconnu : {dm_id}", 404)
