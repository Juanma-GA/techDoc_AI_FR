"""Rapport metriques du moteur word-reviewer sur le corpus de reference.

Outil de dev (couche 3 de fiabilisation) : execute le moteur deterministe sur le
corpus annote et sort precision / rappel / F1 par document et global, pour iterer
les regles/prompts sur des chiffres plutot qu'au feeling.

Usage :
    cd apps/word-reviewer/backend && python ../../scripts/eval_word_reviewer.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permet l'execution depuis apps/word-reviewer/backend.
BACKEND = Path(__file__).resolve().parent.parent / "apps" / "word-reviewer" / "backend"
if BACKEND.exists() and str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def main() -> int:
    from sqlalchemy import select

    from app.core import rules_engine
    from app.core.docx_zones import recognize_zones
    from app.db.models import Document, StandardVersion
    from app.db.session import SessionLocal
    from app.parsers.docx_parser import parse_docx
    from tests.golden.corpus import build_corpus

    db = SessionLocal()
    versions = list(db.scalars(select(StandardVersion)))
    if not versions:
        print("[erreur] Aucun StandardVersion (lance d'abord les migrations + seed).")
        return 1

    g_tp = g_fp = g_fn = 0
    print(f"{'document':<12} {'prec':>6} {'rappel':>7} {'F1':>6}")
    print("-" * 34)
    for gold in build_corpus():
        parsed = recognize_zones(parse_docx(gold.path))
        predicted = {
            r.rule_code
            for r in rules_engine.run_all(parsed, Document(), db, versions)
            if r.rule_kind == "standard"
        }
        tp = len(predicted & gold.expected)
        fp = len(predicted - gold.expected)
        fn = len(gold.expected - predicted)
        g_tp += tp
        g_fp += fp
        g_fn += fn
        prec = tp / (tp + fp) if (tp + fp) else 1.0
        rec = tp / (tp + fn) if (tp + fn) else 1.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        print(f"{gold.name:<12} {prec:>6.2f} {rec:>7.2f} {f1:>6.2f}")
    db.close()

    prec = g_tp / (g_tp + g_fp) if (g_tp + g_fp) else 1.0
    rec = g_tp / (g_tp + g_fn) if (g_tp + g_fn) else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    print("-" * 34)
    print(f"{'GLOBAL':<12} {prec:>6.2f} {rec:>7.2f} {f1:>6.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
