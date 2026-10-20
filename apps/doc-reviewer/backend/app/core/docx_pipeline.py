"""Pipeline de revue **Word natif** (selected by Document.working_format).

Un document `.docx` est parsé en blocs (`docx_parser`), chaque bloc portant un
`target_id` stable `dp<N>`. La détection **réutilise le moteur texte existant**
en présentant les blocs comme des `ParsedPage` (page = index du bloc) : on
appelle `rules_engine.run_all` avec `src_path=None` et vision désactivée, ce qui
exécute catalogue / custom / unités / scan IA + **fiabilisation** et saute
naturellement les contrôles PDF-only (layout géométrique, vision). Les
suggestions sont ensuite matérialisées par `target_id` (pas de bbox), et
appliquées dans le `.docx` par `docx_editor`.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.checks import docx_checks
from app.checks.client_bundle import ClientBundle
from app.checks.client_registry import load_active_client_configuration
from app.checks.raw import RawSuggestion
from app.core import docx_zones, rules_engine
from app.core.compiled_rule_executor import execute_docx_rules
from app.core.compiled_rules import RuleResult
from app.core.rule_applicability import RuleExecutionContext, is_standard_applicable
from app.db.models import Document, StandardVersion, Suggestion
from app.parsers.docx_parser import Block, ParsedDocx
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


def blocks_to_pages(blocks: list[Block]) -> list[ParsedPage]:
    """Présente chaque bloc docx comme une `ParsedPage` (page = index du bloc)
    pour réutiliser les détecteurs texte du pipeline PDF."""
    return [
        ParsedPage(page=b.index, text=b.text or "", spans=[], has_text_layer=bool((b.text or "").strip()))
        for b in blocks
    ]


def as_parsed_pdf(parsed: ParsedDocx) -> ParsedPdf:
    pages = blocks_to_pages(parsed.blocks)
    return ParsedPdf(
        page_count=parsed.block_count,
        pages=pages,
        full_text=parsed.full_text,
        is_signed=False,
    )


def run_docx(
    parsed: ParsedDocx,
    document: Document,
    db: Session,
    standard_versions: Optional[list[StandardVersion]] = None,
    *,
    checklist_enabled: bool = True,
    progress_cb: Optional[Callable[[int], None]] = None,
    warnings: Optional[list[str]] = None,
    compiled_results: Optional[list[RuleResult]] = None,
    client_bundle: ClientBundle[Any] | None = None,
) -> list[RawSuggestion]:
    """Détection sur un document Word natif. `RawSuggestion.page` porte l'index
    du bloc (→ `target_id = dp<page>`).

    Combine :
    - la détection **texte** réutilisée du pipeline PDF (catalogue / custom /
      unités / scan IA + fiabilisation), via les blocs présentés en pseudo-pages ;
    - les contrôles **Word natifs** (barres de révision) qui exploitent les
      métadonnées de suivi de modifications — impossibles sur un PDF.

    Les zones sémantiques (Highlights, Fiche suiveuse, LEP…) sont reconnues au
    préalable (`docx_zones`) pour enrichir l'affichage et le ciblage.
    """
    if client_bundle is None:
        client_bundle = load_active_client_configuration().bundle

    docx_zones.recognize_zones(parsed)  # renseigne Block.semantic_zone (in place)

    pseudo = as_parsed_pdf(parsed)
    # src_path=None -> pas de layout/vision (PDF-only) ; vision override False.
    out = rules_engine.run_all(
        pseudo,
        document,
        db,
        standard_versions or [],
        src_path=None,
        vision_enabled_override=False,
        checklist_enabled=checklist_enabled,
        progress_cb=progress_cb,
        warnings=warnings,
        execute_compiled=False,
        client_bundle=client_bundle,
    )
    execution_context = RuleExecutionContext.from_document(document)
    applicable_versions = [
        version
        for version in standard_versions or []
        if is_standard_applicable(version.standard.code, execution_context)
    ]
    compiled_rules = rules_engine.load_compiled_rules(
        db,
        applicable_versions,
        checklist_enabled=checklist_enabled,
    )
    compiled_rules_for_execution, _compiled_checklist_rules_for_ai = rules_engine.route_compiled_rules(
        compiled_rules,
        checklist_ai_scan=checklist_enabled and rules_engine.get_checklist_ai_scan(db),
    )
    if compiled_rules_for_execution:
        results, compiled_raws = execute_docx_rules(
            parsed.blocks,
            compiled_rules_for_execution,
            db=db,
            document=document,
            client_operations=client_bundle.operations,
            client_entities=client_bundle.mapping.entities,
            warnings=warnings,
        )
        if compiled_results is not None:
            compiled_results.extend(results)
        out.extend(compiled_raws)
    # Checks Word natifs (revision) : toujours actifs sur un docx.
    out.extend(docx_checks.run(parsed))
    return out


def materialize_docx(
    raws: list[RawSuggestion],
    parsed: ParsedDocx,
    document_id: uuid.UUID,
    run_id: uuid.UUID,
) -> list[Suggestion]:
    """Convertit les RawSuggestion docx en lignes ORM `Suggestion` avec
    `target_id` (`dp<index>`) et `span_index` = occurrence dans le bloc. Pas de
    bbox (Word est en flux). `page` reçoit le numéro de page déduit du bloc."""
    block_by_index = {b.index: b for b in parsed.blocks}
    counters: dict[tuple[int, str], int] = defaultdict(int)
    rows: list[Suggestion] = []
    for raw in raws:
        block = block_by_index.get(raw.page)
        if block is None:
            continue
        key = (raw.page, raw.original)
        occ = counters[key]
        counters[key] = occ + 1
        rows.append(
            Suggestion(
                document_id=document_id,
                run_id=run_id,
                rule_kind=raw.rule_kind,
                rule_code=raw.rule_code,
                source_kind=rules_engine.classify_source(
                    raw.rule_kind,
                    raw.rule_code,
                    ai_generated=raw.ai_generated,
                ),
                severity=raw.severity,
                message=raw.message,
                original_text=raw.original,
                proposed_text=raw.proposed,
                page=block.page,
                bbox="{}",
                span_index=occ,
                target_id=block.target_id,
                status="open",
            )
        )
    return rows


def block_view(parsed: ParsedDocx) -> list[dict]:
    """Vue légère des blocs pour le reviewer front. Inclut la zone sémantique
    (Highlights / Fiche suiveuse / LEP…) et l'état de révision Word."""
    docx_zones.recognize_zones(parsed)
    return [
        {
            "target_id": b.target_id,
            "index": b.index,
            "page": b.page,
            "zone": b.zone,
            "semantic_zone": b.semantic_zone or b.zone,
            "kind": b.kind,
            "text": b.text,
            "table_label": b.table_label,
            "revised": b.revised,
            "revision_kind": b.revision_kind or "",
        }
        for b in parsed.blocks
        if (b.text or "").strip()
    ]


def _run_summary(rows: list[Suggestion]) -> str:
    return json.dumps({"total": len(rows)})
