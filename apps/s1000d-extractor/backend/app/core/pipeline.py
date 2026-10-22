"""Orchestrateur du pipeline de migration document -> XML S1000D.

Enchaine les etages independants du format et de la cible :

    parse (adapter) -> IR -> classification contexte -> segmentation forme
        -> resolution candidats -> guidance BREX -> serialisation XML
        -> validation XSD + BREX

Chaque etage emet une progression via `progress_cb` (consommee par le SSE).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core import context_classifier, dm_header, form_segmenter, ingest, resolver, structure_infer
from app.core.brex import parse_brex
from app.core.brex_generation import serialize_with_brex_guidance
from app.core.brex_profile import extract_brex_dm_code
from app.core.ir import IRNode, to_dict

ProgressCb = Callable[[str, int], None]


@dataclass
class PipelineResult:
    tree: dict
    xml: str
    dm_type: str
    issue: str
    violations: list[dict]


def _noop(_step: str, _pct: int) -> None:
    pass


def run(
    path: str | Path,
    *,
    fmt: str,
    issue: str,
    hint: str = "mixed",
    db: Session | None = None,
    brex_xml: str | None = None,
    dm_metadata: dict | None = None,
    header_template: dict | None = None,
    progress_cb: ProgressCb = _noop,
) -> PipelineResult:
    progress_cb("parse", 10)
    blocks = ingest.extract_blocks(path, fmt=fmt, db=db, progress_cb=progress_cb)

    progress_cb("infer", 30)
    root: IRNode = structure_infer.build_ir(blocks)

    progress_cb("context", 45)
    dm_type = context_classifier.classify(root, hint=hint, db=db)
    context_classifier.apply_dm_type(root, dm_type)

    progress_cb("form", 60)
    form_segmenter.segment(root, db=db, progress_cb=lambda pct: progress_cb("form", pct))

    progress_cb("resolve", 75)
    resolver.resolve(root)

    progress_cb("serialize", 85)
    brex_dm_code = extract_brex_dm_code(brex_xml) if brex_xml else None
    brex_rules = parse_brex(brex_xml) if brex_xml else []
    xml, serialization, _brex_guided_candidates = serialize_with_brex_guidance(
        root,
        brex_rules,
        issue=issue,
        dm_type=dm_type,
        dm_metadata=dm_metadata,
        header_template=dm_header.with_brex_dm_code(header_template, brex_dm_code),
    )

    progress_cb("validate", 95)
    violations = _validate(xml, issue=issue, dm_type=dm_type, brex_xml=brex_xml)
    violations.extend(serialization.xsd_violations)

    progress_cb("done", 100)
    return PipelineResult(
        tree=to_dict(root), xml=xml, dm_type=dm_type, issue=issue, violations=violations
    )


def _validate(xml: str, *, issue: str, dm_type: str, brex_xml: str | None) -> list[dict]:
    """Validation XSD + BREX. Import tardif pour ne pas coupler le coeur a lxml
    si la validation est desactivee/indisponible."""
    from app.core.validator import validate_document

    return validate_document(xml, issue=issue, dm_type=dm_type, brex_xml=brex_xml)
