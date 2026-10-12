"""Orchestrateur du pipeline de migration document -> XML S1000D.

Enchaine les etages independants du format et de la cible :

    parse (adapter) -> IR -> classification contexte -> segmentation forme
        -> resolution candidats -> serialisation XML -> validation XSD + BREX

Chaque etage emet une progression via `progress_cb` (consommee par le SSE).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core import context_classifier, form_segmenter, ingest, resolver, structure_infer
from app.core.ir import IRNode, to_dict
from app.core.s1000d_serializer import SerializationDiagnostics, serialize

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
    serialization = SerializationDiagnostics()
    xml = serialize(
        root,
        issue=issue,
        dm_type=dm_type,
        dm_metadata=dm_metadata,
        header_template=header_template,
        diagnostics=serialization,
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
