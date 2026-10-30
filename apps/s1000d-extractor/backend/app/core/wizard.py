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
from time import perf_counter

import structlog
from sqlalchemy.orm import Session

from app.core import (
    context_classifier,
    dm_header,
    form_segmenter,
    ingest,
    resolver,
    splitter,
    structure_infer,
    wizard_response,
)
from app.core import dmrl as dmrl_mod
from app.core import ir as ir_mod
from app.core import preliminary_review as preliminary
from app.core import wizard_resources as wres
from app.core import wizard_split as ws
from app.core.brex import parse_brex
from app.core.brex_generation import serialize_with_brex_guidance
from app.core.brex_profile import extract_brex_dm_code
from app.core.errors import AppError
from app.core.preliminary_projection import reviewed_root, sync_mappings
from app.core.s1000d_serializer import (
    ReferenceIndex,
    build_reference_index,
    missing_data_fields,
)
from app.core.validator import validate_document, xsd_is_valid
from app.core.wizard_zip_export import reference_index_documents
from app.db.models import BrexProfile, Document

STEPS = ("split", "type", "structure", "generate")
# Une DMRL chargee insere une etape de validation AVANT le decoupage : on ne
# decoupe pas sur une liste de DM que l'utilisateur n'a pas encore validee.
STEPS_WITH_DMRL = ("dmrl", *STEPS)
_DEFAULT_LEVEL = "section"

log = structlog.get_logger("s1000d_extractor.wizard")


def steps_for(doc: Document) -> tuple[str, ...]:
    steps = STEPS_WITH_DMRL if doc.dmrl_json else STEPS
    if any(dm["dm_type"] == "procedural" for dm in ws.load_dms(doc)):
        return (*steps[:-1], "preliminary", "generate")
    return steps


# --- helpers d'etat ----------------------------------------------------------

def _brex_xml(
    db: Session, brex_id: str | None, issue: str | None = None
) -> str | None:
    if not brex_id:
        return None
    b = db.get(BrexProfile, brex_id)
    if b is None:
        raise AppError("BREX_NOT_FOUND", "Profil BREX inconnu.", 404)
    if issue is not None and b.s1000d_issue != issue:
        raise AppError(
            "BREX_ISSUE_MISMATCH",
            f"Issue BREX {b.s1000d_issue} differente de l'Issue DM {issue}.",
            422,
        )
    path = Path(b.xml_path)
    if not path.is_file():
        raise AppError("BREX_FILE_NOT_FOUND", "Le fichier du profil BREX est introuvable.", 404)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AppError("BREX_FILE_UNREADABLE", "Le fichier du profil BREX est illisible.", 500) from exc


def images_dir(doc_id: str, *, root: Path | None = None) -> Path:
    """Dossier des illustrations extraites d'un document."""
    if root is None:
        from app.config import settings

        root = Path(settings.storage_dir)
    return root / f"document_{doc_id}_images"


def _extract_illustrations(doc: Document, root: ir_mod.IRNode) -> int:
    """Extrait les images du PDF en JPG et pose l'ICN sur les figures (no-op si
    echec / pas d'image). Le dossier est purge d'abord : relancer l'assistant ne
    doit pas empiler des doublons d'illustrations."""
    from app.core import illustrations
    out_dir = images_dir(doc.id, root=Path(doc.storage_path).parent)
    try:
        if out_dir.exists():
            for old in out_dir.iterdir():
                if old.is_file() and old.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                    old.unlink(missing_ok=True)
        return illustrations.attach_illustrations(
            root,
            pdf_path=doc.pdf_cut_path or doc.storage_path,
            out_dir=out_dir,
            doc_id=doc.id,
            dm_level=splitter.level_of(_DEFAULT_LEVEL),
        )
    except Exception as exc:  # jamais bloquant : le squelette reste generable sans images
        log.warning("wizard_illustrations_failed", error_type=type(exc).__name__)
        return 0


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
        figures = [
            node for node in unit.root.walk()
            if node.kind == "figure" and not node.is_pictogram
        ]
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

    total_started = perf_counter()
    if doc.ir_json:
        preliminary.invalidate_source(doc)
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
    stage_started = perf_counter()
    source_path = prepare_source(
        doc,
        db,
        cut_pdf=cut_pdf,
        start_page=start_page,
        end_page=end_page,
    )
    review_state = preliminary.load(doc)
    review_state["page_offset"] = (
        (doc.pdf_cut_start_page or 1) - 1 if str(source_path) == doc.pdf_cut_path else 0
    )
    doc.preliminary_review_json = json.dumps(review_state, ensure_ascii=False)
    log.info(
        "wizard_stage_timing",
        stage="source_preparation",
        duration_ms=round((perf_counter() - stage_started) * 1000, 1),
        source_format=doc.source_format,
        page_count=doc.page_count,
    )
    progress_cb("parse", 10)
    stage_started = perf_counter()
    blocks = ingest.extract_blocks(
        source_path, fmt=doc.source_format, progress_cb=progress_cb, local_only=True,
    )
    log.info(
        "wizard_stage_timing",
        stage="document_ingest",
        duration_ms=round((perf_counter() - stage_started) * 1000, 1),
        block_count=len(blocks),
    )
    log.info(
        "wizard_source_parsed",
        document_id=doc.id,
        filename=doc.filename,
        block_count=len(blocks),
    )
    progress_cb("infer", 40)
    stage_started = perf_counter()
    root = structure_infer.build_ir(blocks)
    log.info(
        "wizard_stage_timing",
        stage="structure_inference",
        duration_ms=round((perf_counter() - stage_started) * 1000, 1),
        block_count=len(blocks),
    )
    if doc.source_format == "pdf":
        stage_started = perf_counter()
        illustration_count = _extract_illustrations(doc, root)
        log.info(
            "wizard_stage_timing",
            stage="illustration_extraction",
            duration_ms=round((perf_counter() - stage_started) * 1000, 1),
            image_count=illustration_count,
        )
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
    log.info(
        "wizard_stage_timing",
        stage="wizard_total",
        duration_ms=round((perf_counter() - total_started) * 1000, 1),
        dm_count=len(rebuilt_dms),
    )
    return state(doc)


def _resplit(db: Session, doc: Document, split_level: str, progress_cb=_noop_progress) -> None:
    """Recoupe l'IR en DMs et propose un type pour chacun.

    Une DMRL attachee PRIME sur le niveau de titre : le decoupage suit alors la
    liste des DM attendus par le client.
    """
    progress_cb("split", 60)
    split_started = perf_counter()
    root = ir_mod.from_dict(json.loads(doc.ir_json))
    entries = wres.dmrl_data_module_entries(doc)
    units = splitter.split_by_dmrl(root, entries) if entries else splitter.split_into_dms(root, split_level)
    if entries:
        _apply_dmrl_icns(
            units, entries, images_dir(doc.id, root=Path(doc.storage_path).parent),
        )
        doc.ir_json = json.dumps(ir_mod.to_dict(root), ensure_ascii=False)
    log.info(
        "wizard_stage_timing",
        stage="dm_split",
        duration_ms=round((perf_counter() - split_started) * 1000, 1),
        dm_count=len(units),
        dmrl_entry_count=len(entries),
    )
    progress_cb("classify", 80)
    classify_started = perf_counter()
    types = context_classifier.classify_dms(units, hint=doc.context_hint)
    log.info(
        "wizard_stage_timing",
        stage="dm_classification",
        duration_ms=round((perf_counter() - classify_started) * 1000, 1),
        dm_count=len(units),
    )
    dmrl_types = {e.dmc: e.dm_type for e in entries if e.dmc and e.dm_type}
    dms = [
        {
            "dm_id": u.dm_id,
            "dmc": u.dmc,
            "title": u.title,
            # Les types InfoCode 4.1 (ou les choix manuels) priment la classification du contenu.
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
        unresolved_types = wres.unresolved_dmrl_type_entries(doc)
        if unresolved_types:
            raise AppError(
                "DMRL_TYPE_REVIEW_REQUIRED",
                "Choisissez le type a utiliser pour chaque DM en conflit avant de continuer.",
                409,
                detail=[
                    {
                        "dmc": entry.dmc,
                        "title": entry.title,
                        "info_code": entry.info_code,
                    }
                    for entry in unresolved_types
                ],
            )
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
        if "preliminary" in steps_for(doc):
            preliminary.prepare(doc)
            doc.wizard_step = "preliminary"
        else:
            _finish_generation(db, doc)
    elif step == "preliminary":
        preliminary.require_complete(doc)
        _finish_generation(db, doc)
    elif step == "generate":
        preliminary.require_complete(doc)
        return state(doc)
    db.commit()
    return state(doc)


def _finish_generation(db: Session, doc: Document) -> None:
    _generate_all(db, doc)
    doc.wizard_step = "generate"
    doc.status = (
        "incomplete"
        if any(
            dm.get("xsd_valid") is not True
            or dm.get("missing_fields")
            or any(v.get("severity") == "error" for v in dm.get("violations") or [])
            for dm in ws.load_dms(doc)
        )
        else "extracted"
    )


def back(db: Session, doc: Document) -> dict:
    steps = steps_for(doc)
    current_step = doc.wizard_step
    idx = steps.index(doc.wizard_step) if doc.wizard_step in steps else 0
    doc.wizard_step = steps[max(0, idx - 1)]
    if current_step == "generate":
        doc.status = "wizard"
    db.commit()
    return state(doc)


def _apply_types(doc: Document, types: dict) -> None:
    dms = ws.load_dms(doc)
    for dm in dms:
        if dm["dm_id"] in types and types[dm["dm_id"]] in context_classifier.DM_TYPES:
            dm["dm_type"] = types[dm["dm_id"]]
        root = ir_mod.from_dict(dm["tree"])
        context_classifier.apply_dm_type(root, dm["dm_type"])
        form_segmenter.segment(root)
        dm["tree"] = ir_mod.to_dict(root)
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
    preliminary.require_complete(doc)
    dms = ws.load_dms(doc)
    brex_xml = _brex_xml(db, doc.brex_id, doc.s1000d_issue)
    brex_dm_code = extract_brex_dm_code(brex_xml) if brex_xml else None
    brex_rules = parse_brex(brex_xml) if brex_xml else []
    res = wres.load_resources(doc)
    dmrl_by_dmc = {entry.dmc: entry.to_dict() for entry in wres.dmrl_entries(doc) if entry.dmc}
    log.info(
        "wizard_generation_started",
        document_id=doc.id,
        dm_count=len(dms),
    )
    reference_index = build_reference_index(
        reference_index_documents(dms, dmrl_by_dmc, doc.s1000d_issue)
    )
    for dm_index, dm in enumerate(dms, start=1):
        dm_started = perf_counter()
        resources_ms = 0.0
        serialization_ms = 0.0
        validation_ms = 0.0
        stage = "resources"
        stage_started = dm_started
        try:
            enriched, extra = wres.apply_resources(dm, res)
            resources_ms = (perf_counter() - stage_started) * 1000

            stage = "serialization"
            stage_started = perf_counter()
            root = ir_mod.from_dict(enriched["tree"])
            render_root = reviewed_root(doc, dm, root)
            template_missing_fields = enriched.get("missing_fields") or []
            xml, serialization, brex_guided_candidates = serialize_with_brex_guidance(
                render_root,
                brex_rules,
                issue=doc.s1000d_issue,
                dm_type=dm["dm_type"],
                title=dm["title"],
                dm_metadata=dmrl_by_dmc.get(dm.get("dmc"), {"title": dm.get("title", "")}),
                missing_fields=template_missing_fields,
                header_template=dm_header.with_brex_dm_code(
                    res.header_template, brex_dm_code
                ),
                reference_index=reference_index,
                reference_dm_id=dm["dm_id"],
            )
            sync_mappings(root, render_root)
            # `content_html`/`content_xml` ne sont pas persistes : ce sont des
            # rendus derives du tree, ils doubleraient inutilement le JSON.
            dm.update({
                k: v for k, v in enriched.items()
                if k not in ("xml", "violations", "content_html", "content_xml")
            })
            dm["tree"] = ir_mod.to_dict(root)
            dm["xml"] = xml
            dm["template_missing_fields"] = template_missing_fields

            serialization_ms = (perf_counter() - stage_started) * 1000
            stage = "validation"
            stage_started = perf_counter()
            dm["missing_fields"] = missing_data_fields(xml, template_missing_fields)
            dm["violations"] = validate_document(
                xml, issue=doc.s1000d_issue, dm_type=dm["dm_type"], brex_xml=brex_xml,
                brex_rules=res.brex_rules, dm=enriched,
            ) + serialization.xsd_violations + extra
            dm["xsd_valid"] = xsd_is_valid(dm["violations"])
            validation_ms = (perf_counter() - stage_started) * 1000
            log.info(
                "dm_generated",
                document_id=doc.id,
                dm_id=dm["dm_id"],
                dm_index=dm_index,
                dm_count=len(dms),
                icn_count=sum(1 for node in root.walk() if node.kind == "figure" and node.icn),
                has_doctype="<!DOCTYPE dmodule [" in xml,
                xml_length=len(xml),
                brex_guided_candidates=brex_guided_candidates,
                resources_ms=round(resources_ms, 1),
                serialization_ms=round(serialization_ms, 1),
                validation_ms=round(validation_ms, 1),
                total_ms=round((perf_counter() - dm_started) * 1000, 1),
            )
        except Exception as exc:
            failed_phase_ms = (perf_counter() - stage_started) * 1000
            if stage == "resources":
                resources_ms = failed_phase_ms
            elif stage == "serialization":
                serialization_ms = failed_phase_ms
            else:
                validation_ms = failed_phase_ms
            log.exception(
                "dm_generation_failed",
                document_id=doc.id,
                dm_id=dm.get("dm_id"),
                dm_index=dm_index,
                dm_count=len(dms),
                failed_stage=stage,
                resources_ms=round(resources_ms, 1),
                serialization_ms=round(serialization_ms, 1),
                validation_ms=round(validation_ms, 1),
                total_ms=round((perf_counter() - dm_started) * 1000, 1),
            )
            dm["xml"] = None
            dm["violations"] = [{
                "severity": "error", "rule": "GENERATE",
                "message": f"Generation impossible pour ce DM : {exc}", "path": "/",
            }]
            dm["xsd_valid"] = False
    ws.save_dms(doc, dms)


# --- vue d'etat --------------------------------------------------------------

def state(doc: Document) -> dict:
    dms = ws.load_dms(doc)
    steps = steps_for(doc)
    step = doc.wizard_step or steps[0]
    out_dms = [wizard_response.project_dm_state(dm, step) for dm in dms]
    out = {
        "step": step,
        "split_level": doc.split_level or _DEFAULT_LEVEL,
        "dmrl_dm_count": len(wres.dmrl_data_module_entries(doc)),
        "steps": list(steps),
        "can_undo": step == "split" and ws.can_undo(doc),
        "has_brex_profile": bool(doc.brex_id),
        "resources": _resources_state(doc),
        "dms": out_dms,
    }
    if step == "preliminary":
        out["preliminary"] = preliminary.view(doc)
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


def dm_xml(
    doc: Document,
    dm_id: str,
    *,
    db: Session | None = None,
    reference_index: ReferenceIndex | None = None,
) -> str:
    dms = ws.load_dms(doc)
    res = wres.load_resources(doc)
    if doc.brex_id and db is None:
        raise AppError("BREX_SESSION_REQUIRED", "Session de base requise pour charger le BREX.", 500)
    brex_xml = _brex_xml(db, doc.brex_id, doc.s1000d_issue) if db else None
    brex_dm_code = extract_brex_dm_code(brex_xml) if brex_xml else None
    brex_rules = parse_brex(brex_xml) if brex_xml else []
    dmrl_by_dmc = {entry.dmc: entry.to_dict() for entry in wres.dmrl_entries(doc) if entry.dmc}
    if reference_index is None:
        reference_index = build_reference_index(
            reference_index_documents(dms, dmrl_by_dmc, doc.s1000d_issue)
        )
    for dm in dms:
        if dm["dm_id"] == dm_id:
            preliminary.require_complete(doc, dm_id)
            if not dm.get("tree"):
                raise AppError("NO_XML", "XML non genere : termine l'etape Generation.", 409)
            # Le tree est la source de verite : un XML persiste peut provenir
            # d'une generation precedente ou d'un serializer ancien.
            enriched, template_extra = wres.apply_resources(dm, res)
            template_missing_fields = enriched.get("missing_fields") or []
            template_violations = [
                violation for violation in template_extra
                if violation.get("rule") == "TEMPLATE"
            ]
            root = ir_mod.from_dict(enriched["tree"])
            render_root = reviewed_root(doc, dm, root)
            xml, serialization, _brex_guided_candidates = serialize_with_brex_guidance(
                render_root,
                brex_rules,
                issue=doc.s1000d_issue,
                dm_type=dm["dm_type"],
                title=dm["title"],
                dm_metadata=dmrl_by_dmc.get(dm.get("dmc"), {"title": dm.get("title", "")}),
                missing_fields=template_missing_fields,
                header_template=dm_header.with_brex_dm_code(
                    res.header_template, brex_dm_code
                ),
                reference_index=reference_index,
                reference_dm_id=dm["dm_id"],
            )
            sync_mappings(root, render_root)
            dm["tree"] = ir_mod.to_dict(root)
            dm["xml"] = xml
            dm["template_missing_fields"] = template_missing_fields
            xsd_results = validate_document(
                xml, issue=doc.s1000d_issue, dm_type=dm["dm_type"],
                brex_xml=brex_xml,
                brex_rules=res.brex_rules,
                dm=enriched,
            )
            xsd_results.extend(serialization.xsd_violations)
            dm["violations"] = [
                violation for violation in dm.get("violations") or []
                if violation.get("rule") not in {"XSD", "WELLFORMED", "TEMPLATE"}
            ] + xsd_results + template_violations
            dm["xsd_valid"] = xsd_is_valid(xsd_results)
            dm["missing_fields"] = missing_data_fields(
                xml, template_missing_fields,
            )
            doc.status = (
                "incomplete"
                if any(
                    item.get("xsd_valid") is not True
                    or item.get("missing_fields")
                    or any(
                        violation.get("severity") == "error"
                        for violation in item.get("violations") or []
                    )
                    for item in dms
                )
                else "extracted"
            )
            ws.save_dms(doc, dms)
            return xml
    raise AppError("DM_NOT_FOUND", f"DM inconnu : {dm_id}", 404)
