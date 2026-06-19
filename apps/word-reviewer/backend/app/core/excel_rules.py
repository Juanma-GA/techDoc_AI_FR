"""Import d'une checklist client Excel (`Topic | Check`) en regles custom.

Format reel = checklist de revue : une colonne categorie (`Topic`) + une colonne
verification en langage naturel (`Check`). Le mapping de colonnes est
**parametrable** (`COLUMN_ALIASES`) pour absorber d'autres en-tetes sans toucher
au code.

Chaque ligne est **classee** par heuristique vers un `kind` (le tier reste
editable ensuite dans l'UI) :
- items visuels (logo, illustration, barre de revision, OCR, mise en page) -> `manual` ;
- « justifie/justified » -> `style_check` (alignement) ;
- footer/header/highlights/fiche suiveuse -> `llm_nl` scope sur la zone ;
- sinon -> `llm_nl` (le `Check` sert de prompt Mistral).

Les regles deterministes « dures » (raisons sociales, copyright, ATA...) sont
deja couvertes par le catalogue ATA100 builtin : l'import ajoute surtout du
`llm_nl` et du `manual` par-dessus.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from openpyxl import load_workbook  # type: ignore[import-untyped]


# Alias d'en-tetes (minuscules) -> colonne logique. Parametrable.
COLUMN_ALIASES: dict[str, list[str]] = {
    "topic": ["topic", "sujet", "categorie", "catégorie", "theme", "thème", "section"],
    "check": ["check", "check (tools used)", "verification", "vérification", "description", "controle", "contrôle"],
    "severity": ["severity", "severite", "sévérité", "criticite", "criticité"],
}

_MANUAL_KW = [
    "logo", "illustration", "revision bar", "barre de revision", "ocr", "layout",
    "mise en page", "odd", "even", "pair", "impair", "picture", "image", "visual",
    "visuel", "font", "police", "underline", "souligne", "tab", "align character",
    "alignment of characters", "scan", "watermark", "filigrane",
]
_STYLE_JUSTIFY_KW = ["justif"]
_ZONE_KW: dict[str, list[str]] = {
    "footer": ["footer", "pied de page", "copyright"],
    "header": ["header", "en-tete", "en-tête", "entete"],
    "highlights_table": ["highlight", "record of revision"],
    "fiche_suiveuse": ["fiche suiveuse", "follow-up", "follow up"],
    "lep": ["effective pages", "lep", "list of effective"],
}


@dataclass
class ParsedRule:
    name: str
    category: str
    kind: str
    pattern: str
    replacement: str
    target_zone: str
    severity: str
    message: str


def _norm(value: object) -> str:
    return str(value).strip() if value is not None else ""


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


def _classify(check: str) -> tuple[str, str, str]:
    """(kind, target_zone, severity) a partir du texte du Check."""
    low = check.lower()
    severity = "info" if (" should" in f" {low}" or "recommend" in low) else "warning"
    if any(kw in low for kw in _MANUAL_KW):
        zone = ""
        for z, kws in _ZONE_KW.items():
            if any(kw in low for kw in kws):
                zone = z
                break
        return "manual", zone, severity
    if any(kw in low for kw in _STYLE_JUSTIFY_KW):
        return "style_check", "", severity
    for zone, kws in _ZONE_KW.items():
        if any(kw in low for kw in kws):
            return "llm_nl", zone, severity
    return "llm_nl", "", severity


_HEADER_SCAN = 25


def _detect_header_row(grid: list[list[str]]) -> int:
    """Ligne d'en-tete (0-based) = premiere ligne la plus large (max de cellules
    non vides). Les titres au-dessus sont etroits, les donnees ont des trous."""
    counts = [sum(1 for c in r if c and str(c).strip()) for r in grid]
    if not counts or max(counts) == 0:
        return 0
    return counts.index(max(counts))


def list_sheets(data: bytes, sample_rows: int = _HEADER_SCAN, max_cols: int = 40) -> list[dict]:
    """Onglets de l'.xlsx : grille d'apercu (rectangulaire) + ligne d'en-tete
    detectee (0-based). L'UI affiche la grille cliquable pour choisir la ligne
    d'en-tete, puis derive les colonnes (lettre + en-tete) cote client."""
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    out: list[dict] = []
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


def parse_checklist(data: bytes, sheet: str | None = None, mapping: dict | None = None) -> list[ParsedRule]:
    """Construit les regles depuis l'onglet `sheet` (ou actif) selon `mapping`.

    `mapping` (optionnel) : {header_row:int, topic:int|None, check:int,
    context:[int]}. Sans mapping, auto-detection (en-tete Topic|Check devine).
    """
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb[sheet] if (sheet and sheet in wb.sheetnames) else wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []

    if mapping and mapping.get("check") is not None:
        header_idx = int(mapping.get("header_row", 0))
        columns = {"topic": mapping.get("topic"), "check": int(mapping["check"])}
        context_cols = [int(c) for c in (mapping.get("context") or [])]
    else:
        header_idx = 0
        columns = {}
        for i, row in enumerate(rows[:5]):
            cand = _resolve_columns(list(row))
            if "check" in cand:
                header_idx = i
                columns = cand
                break
        if "check" not in columns:
            columns = {"topic": 0, "check": 1}
        context_cols = []

    out: list[ParsedRule] = []
    last_topic = ""
    for row in rows[header_idx + 1:]:
        cells = list(row)

        def at(idx) -> str:
            return _norm(cells[idx]) if idx is not None and 0 <= idx < len(cells) else ""

        topic = at(columns.get("topic")) or last_topic
        if at(columns.get("topic")):
            last_topic = at(columns.get("topic"))
        check = at(columns.get("check"))
        if not check:
            continue
        context = " | ".join(p for p in (at(c) for c in context_cols) if p)
        full = f"{check} | {context}" if context else check
        kind, zone, severity = _classify(check)
        sev_col = at(columns.get("severity")).lower()
        if sev_col in {"error", "erreur", "warning", "info"}:
            severity = {"erreur": "error"}.get(sev_col, sev_col)
        out.append(
            ParsedRule(
                name=full[:500],
                category=topic[:120],
                kind=kind,
                pattern="",
                replacement="",
                target_zone=zone,
                severity=severity,
                message=full,
            )
        )
    return out
