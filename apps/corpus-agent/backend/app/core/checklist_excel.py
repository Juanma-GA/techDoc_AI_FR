"""Import d'une checklist Excel (`.xlsx`/`.xlsm`) en règles personnalisées.

Format attendu = checklist de revue : une colonne catégorie (`Topic`) + une
colonne vérification en langage naturel (`Check`). Le mapping de colonnes est
**paramétrable** (`COLUMN_ALIASES`) pour absorber d'autres en-têtes sans toucher
au code, ou fourni explicitement par l'UI (l'utilisateur clique la ligne
d'en-tête et choisit les colonnes).

Chaque ligne devient une règle personnalisée `{label, consigne, severity}` —
la même forme que celles saisies à la main dans Paramètres et consommées par
`checks/custom_rules.py`. Le `Check` sert de `consigne` (prompt Mistral) ; le
`Topic` sert de `label`. L'import ne fait donc qu'alimenter en masse le store
`regles_personnalisees` existant : aucune nouvelle table, aucun nouveau check.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from openpyxl import load_workbook  # type: ignore[import-untyped]

# Alias d'en-têtes (minuscules) -> colonne logique. Paramétrable.
COLUMN_ALIASES: dict[str, list[str]] = {
    "topic": [
        "topic", "sujet", "categorie", "catégorie", "theme", "thème",
        "section", "libelle", "libellé",
    ],
    "check": [
        "check", "verification", "vérification", "description", "controle",
        "contrôle", "consigne", "regle", "règle", "regles", "règles", "exigence",
    ],
    "severity": [
        "severity", "severite", "sévérité", "criticite", "criticité",
        "gravite", "gravité",
    ],
    # Colonne « prise en compte / type » : `manuel` = verification humaine.
    # corpus-agent n'evalue que par IA : les regles manuelles sont IGNOREES a
    # l'import (voir parse_checklist). Reconnue pour absorber les checklists
    # partagees avec word-reviewer (qui, lui, gere le manuel).
    "handling": [
        "prise en compte", "type", "traitement", "mode", "handling",
        "type de controle", "type de contrôle",
    ],
    # Colonne « contexte » : concatenee a la consigne. `zone` reconnue mais non
    # utilisee (les regles custom corpus-agent n'ont pas de zone cible).
    "context": ["contexte", "context", "commentaire", "note", "precision", "précision"],
    "zone": ["zone", "cible", "emplacement"],
}

# Sévérités internes des règles personnalisées (cf. custom_rules._SEVERITY).
_SEVERITY_ALIASES: dict[str, str] = {
    "faible": "low", "low": "low", "mineur": "low", "info": "low",
    "moyenne": "medium", "moyen": "medium", "medium": "medium", "warning": "medium",
    "haute": "high", "high": "high", "elevee": "high", "élevée": "high",
    "majeur": "high", "critique": "high", "error": "high", "bloquant": "high",
}
# Mots-clés qui montent/descendent la criticité par défaut quand aucune colonne
# de sévérité n'est fournie.
_HIGH_KW = ["doit", "obligatoire", "interdit", "jamais", "must", "shall", "required", "mandatory"]
_LOW_KW = ["devrait", "recommand", "should", "recommend", "preferable", "préférable"]


@dataclass
class ParsedRule:
    label: str
    consigne: str
    severity: str


def _norm(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _cell(cells: list[object], idx: int | None) -> str:
    """Valeur normalisee de la cellule `idx` (ou "" si hors bornes / None)."""
    return _norm(cells[idx]) if idx is not None and 0 <= idx < len(cells) else ""


def _resolve_columns(header: list[object]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(header):
        label = _norm(cell).lower()
        if not label:
            continue
        for logical, aliases in COLUMN_ALIASES.items():
            if logical in mapping:
                continue
            if any(alias == label or alias in label for alias in aliases):
                mapping[logical] = idx
    return mapping


def _classify_severity(check: str) -> str:
    """Criticité par défaut (low/medium/high) d'après le texte du Check."""
    low = check.lower()
    if any(kw in low for kw in _HIGH_KW):
        return "high"
    if any(kw in low for kw in _LOW_KW):
        return "low"
    return "medium"


_HEADER_SCAN = 25


def _detect_header_row(grid: list[list[str]]) -> int:
    """Ligne d'en-tête (0-based) = première ligne la plus large (max de cellules
    non vides). Les titres au-dessus sont étroits, les données ont des trous."""
    counts = [sum(1 for c in r if c and str(c).strip()) for r in grid]
    if not counts or max(counts) == 0:
        return 0
    return counts.index(max(counts))


def list_sheets(data: bytes, sample_rows: int = _HEADER_SCAN, max_cols: int = 40) -> list[dict[str, Any]]:
    """Onglets de l'.xlsx : grille d'aperçu (rectangulaire) + ligne d'en-tête
    détectée (0-based). L'UI affiche la grille cliquable pour choisir la ligne
    d'en-tête, puis dérive les colonnes (lettre + en-tête) côté client."""
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    out: list[dict[str, Any]] = []
    try:
        for ws in wb.worksheets:
            grid: list[list[str]] = []
            for r in ws.iter_rows(min_row=1, max_row=sample_rows, values_only=True):
                grid.append([_norm(c) for c in list(r)[:max_cols]])
            ncols = max((len(r) for r in grid), default=0)
            grid = [r + [""] * (ncols - len(r)) for r in grid]  # rectangulaire
            out.append({"name": ws.title, "header_row": _detect_header_row(grid), "rows": grid})
    finally:
        wb.close()
    return out


def parse_checklist(
    data: bytes, sheet: str | None = None, mapping: dict[str, Any] | None = None,
) -> list[ParsedRule]:
    """Construit les règles depuis l'onglet `sheet` (ou actif) selon `mapping`.

    `mapping` (optionnel) : {header_row:int, topic:int|None, check:int,
    context:[int], severity:int|None}. Sans mapping, auto-détection (en-tête
    Topic|Check devinée via `COLUMN_ALIASES`).
    """
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb[sheet] if (sheet and sheet in wb.sheetnames) else wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []

    if mapping and mapping.get("check") is not None:
        header_idx = int(mapping.get("header_row", 0))
        columns: dict[str, int | None] = {
            "topic": mapping.get("topic"),
            "check": int(mapping["check"]),
            "severity": mapping.get("severity"),
        }
        context_cols = [int(c) for c in (mapping.get("context") or [])]
    else:
        header_idx = 0
        columns = {}
        for i, row in enumerate(rows[:5]):
            cand = _resolve_columns(list(row))
            if "check" in cand:
                header_idx = i
                columns = dict(cand)
                break
        if "check" not in columns:
            columns = {"topic": 0, "check": 1}
        # Colonne « contexte » nommee -> concatenee a la consigne.
        context_cols = [columns["context"]] if columns.get("context") is not None else []

    out: list[ParsedRule] = []
    last_topic = ""
    for row in rows[header_idx + 1:]:
        cells = list(row)
        raw_topic = _cell(cells, columns.get("topic"))
        topic = raw_topic or last_topic
        if raw_topic:
            last_topic = raw_topic
        check = _cell(cells, columns.get("check"))
        if not check:
            continue
        # corpus-agent n'evalue que par IA : on ignore les regles marquees
        # « manuel » (verification humaine, non applicable ici).
        handling = _cell(cells, columns.get("handling")).lower()
        if handling in {"manuel", "manual", "humain", "human", "a la main"}:
            continue
        context = " | ".join(p for p in (_cell(cells, c) for c in context_cols) if p)
        consigne = f"{check} | {context}" if context else check
        sev_cell = _cell(cells, columns.get("severity")).lower()
        severity = _SEVERITY_ALIASES.get(sev_cell, _classify_severity(check))
        out.append(
            ParsedRule(
                label=(topic or "Règle importée")[:120],
                consigne=consigne[:2000],
                severity=severity,
            )
        )
    return out
