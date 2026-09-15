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

import structlog
from sqlalchemy.orm import Session

from app.core import context_classifier, ingest, resolver, splitter, structure_infer
from app.core import dmrl as dmrl_mod
from app.core import ir as ir_mod
from app.core import wizard_resources as wres
from app.core import wizard_split as ws
from app.core.errors import AppError
from app.core.s1000d_serializer import serialize
from app.core.validator import validate_document
from app.db.models import BrexProfile, Document

STEPS = ("split", "type", "structure", "generate")
# Une DMRL chargee insere une etape de validation AVANT le decoupage : on ne
# decoupe pas sur une liste de DM que l'utilisateur n'a pas encore validee.
STEPS_WITH_DMRL = ("dmrl", *STEPS)
_DEFAULT_LEVEL = "section"

log = structlog.get_logger("s1000d_extractor.wizard")


def steps_for(doc: Document) -> tuple[str, ...]:
    return STEPS_WITH_DMRL if doc.dmrl_json else STEPS


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
    echec / pas d'image). Le dossier est purge d'abord : relancer l'assistant ne
    doit pas empiler des doublons d'illustrations."""
    from app.core import illustrations
    out_dir = images_dir(doc.id)
    try:
        if out_dir.exists():
            for old in out_dir.iterdir():
                if old.is_file() and old.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                    old.unlink(missing_ok=True)
        illustrations.attach_illustrations(
            root, pdf_path=doc.pdf_cut_path or doc.storage_path, out_dir=out_dir, doc_id=doc.id
        )
    except Exception:  # jamais bloquant : le squelette reste generable sans images
        pass


def _apply_dmrl_icns(
    units: list[splitter.DmUnit],
    entries: list[dmrl_mod.DmrlEntry],
    out_dir: Path,
) -> None:
    from app.core import illustrations

    for unit in units:
        if unit.dmrl_index is None or unit.dmrl_index >= len(entries):
            continue
        icn_names = dmrl_mod.extract_icn_filenames(entries[unit.dmrl_index].icn)
        if not icn_names:
            continue
        figures = [node for node in unit.root.walk() if node.kind == "figure"]
        for figure, icn_name in zip(figures, icn_names, strict=False):
            current_name = figure.icn or (figure.icns[0] if figure.icns else None)
            if not current_name:
                continue
            renamed = illustrations.rename_illustration(out_dir, current_name, icn_name)
            if renamed:
                figure.icn = renamed
                figure.icns = [renamed]


# --- transitions -------------------------------------------------------------

def _noop_progress(step: str, pct: int) -> None:
    pass


def start(
    db: Session,
    doc: Document,
    progress_cb=_noop_progress,
    *,
    cut_pdf: bool = True,
    start_page: int | None = None,
    end_page: int | None = None,
) -> dict:
    """Parse le document, construit l'IR, propose un decoupage par defaut.

    `progress_cb(step, pct)` permet de streamer la progression (parse / ocr /
    infer / split / classify) vers une barre cote UI.
    """
    from app.core.pdf_cut import prepare_source

    previous_dm_count = len(ws.load_dms(doc))
    doc.dms_json = "[]"
    doc.dms_history_json = None
    log.info(
        "wizard_rebuild_started",
        document_id=doc.id,
        filename=doc.filename,
        source_format=doc.source_format,
        previous_dm_count=previous_dm_count,
        cut_pdf=cut_pdf,
        start_page=start_page,
        end_page=end_page,
    )
    source_path = prepare_source(
        doc,
        db,
        cut_pdf=cut_pdf,
        start_page=start_page,
        end_page=end_page,
    )
    progress_cb("parse", 10)
    blocks = ingest.extract_blocks(
        source_path, fmt=doc.source_format, db=db, progress_cb=progress_cb
    )
    log.info(
        "wizard_source_parsed",
        document_id=doc.id,
        filename=doc.filename,
        block_count=len(blocks),
    )
    progress_cb("infer", 40)
    root = structure_infer.build_ir(blocks)
    if doc.source_format == "pdf":
        _extract_illustrations(doc, root)
    doc.ir_json = json.dumps(ir_mod.to_dict(root), ensure_ascii=False)
    doc.split_level = _DEFAULT_LEVEL
    ws.reset_history(doc)                      # nouvel assistant -> pile undo vide
    _resplit(db, doc, _DEFAULT_LEVEL, progress_cb=progress_cb)
    rebuilt_dms = ws.load_dms(doc)
    log.info(
        "wizard_split_completed",
        document_id=doc.id,
        filename=doc.filename,
        new_dm_count=len(rebuilt_dms),
        dm_ids=[dm["dm_id"] for dm in rebuilt_dms[:5]],
    )
    doc.wizard_step = steps_for(doc)[0]
    doc.status = "wizard"
    log.info(
        "wizard_started",
        document_id=doc.id,
        filename=doc.filename,
        dm_count=len(ws.load_dms(doc)),
        step=doc.wizard_step,
    )
    progress_cb("done", 100)
    db.commit()
    return state(doc)


def _resplit(db: Session, doc: Document, split_level: str, progress_cb=_noop_progress) -> None:
    """Recoupe l'IR en DMs et propose un type pour chacun.

    Une DMRL attachee PRIME sur le niveau de titre : le decoupage suit alors la
    liste des DM attendus par le client.
    """
    progress_cb("split", 60)
    root = ir_mod.from_dict(json.loads(doc.ir_json))
    entries = wres.dmrl_entries(doc)
    units = splitter.split_by_dmrl(root, entries) if entries else splitter.split_into_dms(root, split_level)
    if entries:
        _apply_dmrl_icns(units, entries, images_dir(doc.id))
        doc.ir_json = json.dumps(ir_mod.to_dict(root), ensure_ascii=False)
    progress_cb("classify", 80)
    types = context_classifier.classify_dms(units, hint=doc.context_hint, db=db)
    dmrl_types = {e.dmc: e.dm_type for e in entries if e.dmc and e.dm_type}
    dms = [
        {
            "dm_id": u.dm_id,
            "dmc": u.dmc,
            "title": u.title,
            # Le type declare dans la DMRL fait foi quand il existe.
            "dm_type": dmrl_types.get(u.dmc) or types[u.dm_id],
            "is_orphan": u.is_orphan,
            "tree": ir_mod.to_dict(u.root),
            "xml": None,
            "violations": None,
        }
        for u in units
    ]
    if entries:
        ws.sync_dmcs(dms, doc)
    ws.save_dms(doc, dms)
    doc.split_level = split_level


def update(db: Session, doc: Document, params: dict) -> dict:
    """Recalcule l'etape courante avec de nouveaux parametres (sans avancer).

    A l'etape split : `op` (edition manuelle / masquage / undo) ou `split_level`
    (re-analyse complete qui ecrase les ajustements). L'historique undo n'est
    empile qu'ICI, jamais dans `_resplit`/`apply_split_op` (partages avec
    `start`/`advance`)."""
    if doc.wizard_step == "dmrl":
        wres.apply_dmrl_op(doc, params)
        db.commit()
    elif doc.wizard_step == "split":
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
    if step == "dmrl":
        # La DMRL validee (eventuellement editee) pilote le decoupage.
        _resplit(db, doc, doc.split_level or _DEFAULT_LEVEL)
        doc.wizard_step = "split"
    elif step == "split":
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
    steps = steps_for(doc)
    idx = steps.index(doc.wizard_step) if doc.wizard_step in steps else 0
    doc.wizard_step = steps[max(0, idx - 1)]
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
    """Serialise et valide chaque DM. Etape 100% deterministe : aucun appel IA
    ici (un appel LLM pendant la generation/validation faisait remonter une
    "Unexpected server error" au moindre incident reseau).

    Un DM qui echoue ne casse plus toute l'etape : il porte sa propre violation.
    """
    dms = ws.load_dms(doc)
    brex_xml = _brex_xml(db, doc.brex_id)
    res = wres.load_resources(doc)
    dmrl_by_dmc = {entry.dmc: entry.to_dict() for entry in wres.dmrl_entries(doc) if entry.dmc}
    log.info(
        "wizard_generation_started",
        document_id=doc.id,
        dm_count=len(dms),
    )
    figure_offset = 0
    table_offset = 0
    for dm in dms:
        try:
            enriched, extra = wres.apply_resources(dm, res)
            root = ir_mod.from_dict(enriched["tree"])
            xml = serialize(
                root,
                issue=doc.s1000d_issue,
                dm_type=dm["dm_type"],
                title=dm["title"],
                figure_offset=figure_offset,
                table_offset=table_offset,
                dm_metadata=dmrl_by_dmc.get(dm.get("dmc"), {"title": dm.get("title", "")}),
                header_template=res.header_template,
            )
            figure_offset += sum(1 for node in root.walk() if node.kind == "figure")
            table_offset += sum(1 for node in root.walk() if node.kind == "table")
            # `content_html`/`content_xml` ne sont pas persistes : ce sont des
            # rendus derives du tree, ils doubleraient inutilement le JSON.
            dm.update({
                k: v for k, v in enriched.items()
                if k not in ("xml", "violations", "content_html", "content_xml")
            })
            dm["xml"] = xml
            dm["violations"] = validate_document(
                xml, issue=doc.s1000d_issue, brex_xml=brex_xml,
                brex_rules=res.brex_rules, dm=enriched,
            ) + extra
            log.info(
                "dm_generated",
                document_id=doc.id,
                dm_id=dm["dm_id"],
                icn_count=sum(1 for node in root.walk() if node.kind == "figure" and node.icn),
                has_doctype="<!DOCTYPE dmodule [" in xml,
                xml_length=len(xml),
            )
        except Exception as exc:
            log.exception("dm_generation_failed", document_id=doc.id, dm_id=dm.get("dm_id"))
            dm["xml"] = None
            dm["violations"] = [{
                "severity": "error", "rule": "GENERATE",
                "message": f"Generation impossible pour ce DM : {exc}", "path": "/",
            }]
    ws.save_dms(doc, dms)


# --- vue d'etat --------------------------------------------------------------

def state(doc: Document) -> dict:
    dms = ws.load_dms(doc)
    steps = steps_for(doc)
    step = doc.wizard_step or steps[0]
    out_dms = []
    for dm in dms:
        entry = {
            "dm_id": dm["dm_id"],
            "dmc": dm.get("dmc", ""),
            "title": dm["title"],
            "dm_type": dm["dm_type"],
            "is_orphan": bool(dm.get("is_orphan")),
            "node_count": ws.node_count(dm["tree"]),
        }
        if step == "split":
            entry["preview"] = ws.dm_preview(dm["tree"])
        if step == "structure":
            entry["tree"] = dm["tree"]
        if step == "generate":
            entry["violation_count"] = len(dm.get("violations") or [])
            entry["has_xml"] = bool(dm.get("xml"))
            entry["missing_fields"] = dm.get("missing_fields") or []
            entry["cir_unresolved"] = dm.get("cir_unresolved") or []
        out_dms.append(entry)
    out = {
        "step": step,
        "split_level": doc.split_level or _DEFAULT_LEVEL,
        "steps": list(steps),
        "can_undo": step == "split" and ws.can_undo(doc),
        "resources": _resources_state(doc),
        "dms": out_dms,
    }
    if step == "dmrl":
        out["dmrl"] = wres.dmrl_report(doc)
    return out


def _resources_state(doc: Document) -> dict:
    """Etat REEL des ressources : une ressource attachee mais illisible ne doit
    pas s'afficher comme active."""
    res = wres.load_resources(doc) if (doc.cir_path or doc.brex_rules_path or doc.dm_header_json) else None
    return {
        "dmrl_count": len(wres.dmrl_entries(doc)),
        "has_cir": bool(res and res.cir),
        "has_brex_rules": bool(res and res.brex_rules),
        "has_dm_header": bool(res and res.header_template),
        "errors": list(res.errors) if res else [],
    }


def dm_xml(doc: Document, dm_id: str) -> str:
    dms = ws.load_dms(doc)
    figure_offset = 0
    table_offset = 0
    res = wres.load_resources(doc)
    dmrl_by_dmc = {entry.dmc: entry.to_dict() for entry in wres.dmrl_entries(doc) if entry.dmc}
    for dm in dms:
        if dm["dm_id"] == dm_id:
            if not dm.get("tree"):
                raise AppError("NO_XML", "XML non genere : termine l'etape Generation.", 409)
            # Le tree est la source de verite : un XML persiste peut provenir
            # d'une generation precedente ou d'un serializer ancien.
            xml = serialize(
                ir_mod.from_dict(dm["tree"]),
                issue=doc.s1000d_issue,
                dm_type=dm["dm_type"],
                title=dm["title"],
                figure_offset=figure_offset,
                table_offset=table_offset,
                dm_metadata=dmrl_by_dmc.get(dm.get("dmc"), {"title": dm.get("title", "")}),
                header_template=res.header_template,
            )
            dm["xml"] = xml
            ws.save_dms(doc, dms)
            return xml
        root = ir_mod.from_dict(dm["tree"]) if dm.get("tree") else None
        if root is not None:
            figure_offset += sum(1 for node in root.walk() if node.kind == "figure")
            table_offset += sum(1 for node in root.walk() if node.kind == "table")
    raise AppError("DM_NOT_FOUND", f"DM inconnu : {dm_id}", 404)
