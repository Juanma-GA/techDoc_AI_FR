"""Controle LLM du remplissage : relecture independante du PDF + diff.

Le deterministe reste la source de verite. Le LLM relit le PDF de son cote
(`pdf_table.llm_reextract`) et on DIFFE les deux extractions par FIG REP pour
signaler les lignes douteuses avant export :

  - `ok`       : meme FIG REP, champs cles concordants,
  - `warning`  : meme FIG REP, un ou plusieurs champs divergent (ref/qty),
  - `missing`  : le LLM a vu un article que le deterministe n'a pas,
  - `extra`    : le deterministe a un article que le LLM n'a pas vu.

Fonctions PURES et testables sans appel reseau : `diff_items` prend deux listes
d'articles ; `run_challenge` orchestre relecture LLM + diff. Degradation
gracieuse : si le LLM est indisponible, `run_challenge` renvoie un rapport
`status="skipped"` (jamais d'exception, jamais de 5xx).
"""

from __future__ import annotations

from typing import Any

from app.core.column_map import norm

# Champs "durs" compares strictement (apres normalisation).
_HARD_FIELDS = ("ref_client", "ref_interne", "ref_fournisseur", "qty")


def _fig_key(item: dict) -> str:
    return norm(item.get("fig"))


def _norm_val(v: object) -> str:
    return norm(v).replace(" ", "")


def diff_items(deterministic: list[dict], llm: list[dict]) -> dict[str, Any]:
    """Diffe deux extractions par FIG REP. Fonction pure."""
    det_by_fig: dict[str, dict] = {}
    for it in deterministic:
        k = _fig_key(it)
        if k:
            det_by_fig.setdefault(k, it)
    llm_by_fig: dict[str, dict] = {}
    for it in llm:
        k = _fig_key(it)
        if k:
            llm_by_fig.setdefault(k, it)

    rows: list[dict[str, Any]] = []
    counts = {"ok": 0, "warning": 0, "missing": 0, "extra": 0}

    # Articles deterministes : ok / warning / extra (non vus par le LLM).
    for fig, det in det_by_fig.items():
        counterpart = llm_by_fig.get(fig)
        if counterpart is None:
            counts["extra"] += 1
            rows.append({"fig": det.get("fig", ""), "verdict": "extra", "issues": []})
            continue
        issues = []
        for field in _HARD_FIELDS:
            dv, lv = _norm_val(det.get(field)), _norm_val(counterpart.get(field))
            # On ne signale que si les DEUX ont une valeur et qu'elles different.
            if dv and lv and dv != lv:
                issues.append({"field": field, "deterministic": str(det.get(field) or ""),
                               "llm": str(counterpart.get(field) or "")})
        verdict = "warning" if issues else "ok"
        counts[verdict] += 1
        rows.append({"fig": det.get("fig", ""), "verdict": verdict, "issues": issues})

    # Articles vus par le LLM mais absents du deterministe : missing.
    for fig, lit in llm_by_fig.items():
        if fig not in det_by_fig:
            counts["missing"] += 1
            rows.append({
                "fig": lit.get("fig", ""),
                "verdict": "missing",
                "issues": [],
                "llm_only": {f: str(lit.get(f) or "") for f in ("description", *_HARD_FIELDS)},
            })

    total = len(rows)
    summary = {**counts, "total": total}
    # Un remplissage est "propre" s'il n'y a ni ecart ni manque ni extra.
    summary["clean"] = counts["warning"] == 0 and counts["missing"] == 0 and counts["extra"] == 0
    return {"status": "done", "method": "llm_diff", "summary": summary, "rows": rows}


def skipped_report(reason: str) -> dict[str, Any]:
    return {"status": "skipped", "reason": reason, "summary": {}, "rows": []}


def run_challenge(pdf_path: str, deterministic_items: list[dict], mistral: Any) -> dict[str, Any]:
    """Relecture LLM independante + diff. Degradation gracieuse si LLM absent."""
    if mistral is None:
        return skipped_report("LLM desactive")
    # Import local pour eviter un cycle (pdf_table importe column_map, pas challenge).
    from app.parsers.pdf_table import llm_reextract

    llm_items = llm_reextract(pdf_path, mistral)
    if not llm_items:
        return skipped_report("relecture LLM indisponible")
    return diff_items(deterministic_items, llm_items)
