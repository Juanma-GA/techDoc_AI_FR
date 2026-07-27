"""Calcul DETERMINISTE des annees d'experience professionnelle.

Le LLM se contente d'EXTRAIRE les periodes datees (debut/fin de chaque poste,
+ flag stage) ; la somme est faite ici en Python -> resultat stable et
reproductible d'un run a l'autre (fini le "4 ans un coup, 5 ans l'autre").

Regles :
- les stages/alternances sont exclus (flag `internship`) ;
- les periodes qui se chevauchent ne sont PAS comptees deux fois (fusion) ;
- une fin absente / "present" est ramenee a la date du jour (`today`).
"""

from __future__ import annotations

import re
from datetime import date

_PRESENT = {"", "present", "présent", "current", "en cours", "aujourd'hui", "now", "actuel"}


def _parse_ym(value: object) -> int | None:
    """Convertit 'YYYY-MM' ou 'YYYY' en index de mois absolu (annee*12+mois-1).
    Renvoie None si non parsable."""
    if not isinstance(value, str):
        return None
    m = re.match(r"\s*(\d{4})(?:[-/](\d{1,2}))?", value.strip())
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else 1
    if not (1 <= month <= 12) or not (1900 <= year <= 2100):
        return None
    return year * 12 + (month - 1)


def _merge_and_sum_months(intervals: list[tuple[int, int]]) -> int:
    """Somme des durees (en mois) d'intervalles [start, end) fusionnes pour ne
    pas compter deux fois les chevauchements."""
    if not intervals:
        return 0
    ordered = sorted(intervals)
    total = 0
    cur_start, cur_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= cur_end:  # chevauchement ou contigu
            cur_end = max(cur_end, end)
        else:
            total += cur_end - cur_start
            cur_start, cur_end = start, end
    total += cur_end - cur_start
    return total


def years_from_periods(
    periods: list[dict], *, today: date | None = None
) -> float | None:
    """Total d'annees d'experience pro a partir de periodes datees.

    `periods` : liste de dicts {start: 'YYYY-MM'|'YYYY', end: idem|'present'|None,
    internship: bool}. Renvoie un float arrondi a 1 decimale, ou None si aucune
    periode exploitable (l'appelant n'injecte alors rien -> comportement actuel).
    """
    ref = today or date.today()
    now_idx = ref.year * 12 + (ref.month - 1) + 1  # +1 : mois courant inclus
    intervals: list[tuple[int, int]] = []
    for p in periods or []:
        if not isinstance(p, dict) or p.get("internship"):
            continue
        start = _parse_ym(p.get("start"))
        if start is None:
            continue
        end_raw = p.get("end")
        if end_raw is None or (isinstance(end_raw, str) and end_raw.strip().lower() in _PRESENT):
            end = now_idx
        else:
            parsed = _parse_ym(end_raw)
            end = parsed + 1 if parsed is not None else None  # mois de fin inclus
        if end is None or end <= start:
            continue
        intervals.append((start, end))
    if not intervals:
        return None
    months = _merge_and_sum_months(intervals)
    return round(months / 12, 1)


def format_years(years: float) -> str:
    """Formate un nombre d'annees sans '.0' superflu : 5.0 -> '5', 4.5 -> '4.5'."""
    return f"{years:g}"
