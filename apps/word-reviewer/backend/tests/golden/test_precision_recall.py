"""Harnais de non-regression : precision / rappel du moteur deterministe.

Execute `run_all` (deterministe seul, pas de LLM) sur le corpus annote et exige
precision et rappel au-dessus d'un seuil. Detecte les regressions silencieuses
quand on ajuste une regle.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core import rules_engine
from app.core.docx_zones import recognize_zones
from app.db.models import Document, StandardVersion
from app.db.session import SessionLocal
from app.parsers.docx_parser import parse_docx
from tests.golden.corpus import build_corpus


def _predicted_codes(db, versions, path: str) -> set[str]:
    """Codes deterministes (catalogue ATA100) predits : on ignore les regles
    custom eventuelles pour mesurer le moteur builtin de maniere isolee."""
    parsed = recognize_zones(parse_docx(path))
    raws = rules_engine.run_all(parsed, Document(), db, versions)
    return {r.rule_code for r in raws if r.rule_kind == "standard"}


def test_precision_recall_above_threshold():
    db = SessionLocal()
    versions = list(db.scalars(select(StandardVersion)))
    tp = fp = fn = 0
    details = []
    for gold in build_corpus():
        predicted = _predicted_codes(db, versions, gold.path)
        tp += len(predicted & gold.expected)
        fp += len(predicted - gold.expected)
        fn += len(gold.expected - predicted)
        details.append((gold.name, sorted(predicted), sorted(gold.expected)))
    db.close()

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    assert precision >= 0.9, f"precision={precision:.2f} details={details}"
    assert recall >= 0.9, f"recall={recall:.2f} details={details}"
