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
    "check": [
        "check", "check (tools used)", "verification", "vérification", "description",
        "controle", "contrôle", "regle", "règle", "regles", "règles", "exigence",
        "point de controle", "point de contrôle",
    ],
    "severity": ["severity", "severite", "sévérité", "criticite", "criticité", "gravite", "gravité"],
    # Colonne « mode de prise en compte » : manuel = verification humaine (kind
    # `manual`, pas d'evaluation IA) ; auto/ia = evaluation LLM.
    "handling": [
        "prise en compte", "type", "traitement", "mode", "handling",
        "type de controle", "type de contrôle",
    ],
    "zone": ["zone", "cible", "emplacement", "section cible"],
    "context": ["contexte", "context", "commentaire", "note", "precision", "précision"],
}

_MANUAL_KW = [
    "logo", "illustration", "revision bar", "barre de revision", "ocr", "layout",
    "mise en page", "odd", "even", "pair", "impair", "picture", "image", "visual",
    "visuel", "font", "police", "underline", "souligne", "tab", "align character",
    "alignment of characters", "scan", "watermark", "filigrane",
]
# Valeurs de la colonne « prise en compte » signalant une verification humaine.
_MANUAL_HANDLING = {"manuel", "manual", "humain", "human", "a la main", "à la main"}
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
    sheet: str
    row_number: int
    check: str
    handling: str
    context: str
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


def _cell(cells: list[object], idx: object) -> str:
    """Valeur normalisee de la cellule `idx` (ou "" si None / hors bornes)."""
    if idx is None or not isinstance(idx, int) or not 0 <= idx < len(cells):
        return ""
    return _norm(cells[idx])


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

    En mode mapping, seules topic/check sont imposees : les colonnes a role special
    (prise en compte, severite, zone) sont detectees par nom d'en-tete, et TOUTES
    les autres colonnes du modele sont ajoutees au texte de la regle (contexte).
    Les cellules vides sont simplement ignorees.
    """
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb[sheet] if (sheet and sheet in wb.sheetnames) else wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []

    if mapping and mapping.get("check") is not None:
        header_idx = int(mapping.get("header_row", 0))
        header_cells = list(rows[header_idx]) if 0 <= header_idx < len(rows) else []
        # topic/check sont imposes par l'utilisateur ; on detecte EN PLUS, par nom
        # d'en-tete, les colonnes a role special (prise en compte, severite, zone)
        # pour qu'elles gardent leur sens meme en mode mapping.
        named = _resolve_columns(header_cells)
        # Chaque role : valeur explicite si mappee, sinon detection par nom d'en-tete.
        def _role(key: str):
            v = mapping.get(key)
            return v if v is not None else named.get(key)

        columns = {
            "topic": mapping.get("topic"),
            "check": int(mapping["check"]),
            "handling": _role("handling"),
            "severity": _role("severity"),
            "zone": _role("zone"),
        }
        # « Prendre en compte toutes les colonnes du modele » : toute colonne SANS
        # role (ni sujet, ni regle, ni handling/severite/zone) est ajoutee au texte
        # de la regle. Cellules vides ignorees a la lecture (plus bas).
        explicit_ctx = [int(c) for c in (mapping.get("context") or [])]
        if explicit_ctx:
            context_cols = explicit_ctx
        else:
            special = {columns.get(k) for k in ("topic", "check", "handling", "severity", "zone")}
            context_cols = [c for c in range(len(header_cells)) if c not in special]
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
        # Colonne « contexte » nommee -> concatenee au message comme un context_col.
        context_cols = [columns["context"]] if columns.get("context") is not None else []

    # Anti-doublon : une colonne « contexte » qui pointe sur la colonne check (ou
    # topic) reproduirait le libelle -> "texte | texte". On ecarte ces index.
    _excluded_ctx = {columns.get("check"), columns.get("topic")}
    context_cols = [c for c in context_cols if c not in _excluded_ctx]

    out: list[ParsedRule] = []
    last_topic = ""
    for row_number, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        cells = list(row)
        raw_topic = _cell(cells, columns.get("topic"))
        topic = raw_topic or last_topic
        if raw_topic:
            last_topic = raw_topic
        check = _cell(cells, columns.get("check"))
        if not check:
            continue
        # Dedup par contenu : on ne concatene que les parts non vides ET distinctes
        # du check (une autre colonne peut porter un texte identique -> doublon).
        check_key = check.strip().lower()
        parts = [
            p for p in (_cell(cells, c) for c in context_cols)
            if p and p.strip().lower() != check_key
        ]
        context = " | ".join(parts)
        full = f"{check} | {context}" if context else check
        # _classify sert a deduire zone + severite par mots-cles. Le `kind` final
        # ne depend QUE de la colonne explicite « prise en compte » : manuel ->
        # verif humaine (`manual`), sinon `llm_nl` (comportement historique de
        # l'import : tout est confie a l'IA). Pas de colonne -> tout llm_nl.
        _, zone, severity = _classify(check)
        zone_col = _cell(cells, columns.get("zone"))
        if zone_col:
            zone = zone_col
        handling = _cell(cells, columns.get("handling")).lower()
        kind = "manual" if handling in _MANUAL_HANDLING else "llm_nl"
        sev_col = _cell(cells, columns.get("severity")).lower()
        if sev_col in {"error", "erreur", "warning", "info"}:
            severity = {"erreur": "error"}.get(sev_col, sev_col)
        out.append(
            ParsedRule(
                sheet=ws.title,
                row_number=row_number,
                check=check,
                handling=handling,
                context=context,
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


def has_severity_column(data: bytes, sheet: str | None = None, mapping: dict | None = None) -> bool:
    """Vrai si la checklist expose une colonne severite explicite.

    Sert a decider si l'IA doit attribuer la severite a l'import (regle : IA
    seulement quand la colonne n'existe pas). En mode mapping (UI), la severite
    n'est pas transmise -> repose sur l'auto-detection de l'en-tete.
    """
    if mapping is not None and mapping.get("severity") is not None:
        return True
    # Sinon on detecte par nom d'en-tete (vrai dans les deux modes : en mode mapping
    # la severite n'est pas transmise mais peut exister comme colonne nommee).
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb[sheet] if (sheet and sheet in wb.sheetnames) else wb.active
        rows = [list(r) for r in ws.iter_rows(min_row=1, max_row=_HEADER_SCAN, values_only=True)]
        wb.close()
    except Exception:  # noqa: BLE001
        return False
    return any("severity" in _resolve_columns(row) for row in rows)
