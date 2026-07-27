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

from app.core.xlsx_normalize import normalize_xlsx_bytes

# Alias d'en-têtes (minuscules) -> colonne logique. Paramétrable.
COLUMN_ALIASES: dict[str, list[str]] = {
    "topic": [
        "topic", "sujet", "categorie", "catégorie", "theme", "thème",
        "section", "libelle", "libellé", "domaine", "rubrique", "chapitre",
        "famille", "type de controle", "type de contrôle",
    ],
    "check": [
        "check", "verification", "vérification", "description", "controle",
        "contrôle", "consigne", "regle", "règle", "regles", "règles", "exigence",
        "critere", "critère", "point de controle", "point de contrôle",
        "question", "item", "attendu", "descriptif", "intitule", "intitulé",
        "objet", "libelle du controle", "libellé du contrôle",
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


def _severity_from_cell(sev_cell: str) -> str | None:
    """Sévérité (low/medium/high) lue dans la colonne « criticité », ou None si
    la cellule n'évoque rien de connu.

    Match exact d'abord, puis repli sur le plus long alias dont la cellule est
    un dérivé (« majeure » -> « majeur », « mineures » -> « mineur »). Les
    tableaux FR accordent l'adjectif avec « criticité » (nom féminin) : un
    lookup strictement exact rate donc la graphie la plus courante.
    """
    if not sev_cell:
        return None
    exact = _SEVERITY_ALIASES.get(sev_cell)
    if exact is not None:
        return exact
    # Plus long alias préfixe -> insensible à l'ordre du dictionnaire.
    best = ""
    for alias in _SEVERITY_ALIASES:
        if sev_cell.startswith(alias) and len(alias) > len(best):
            best = alias
    return _SEVERITY_ALIASES[best] if best else None


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


def _open_or_none(data: bytes, *, read_only: bool):
    """Ouvre le classeur et le renvoie s'il a au moins un onglet, sinon None."""
    try:
        wb = load_workbook(io.BytesIO(data), read_only=read_only, data_only=True)
        if wb.worksheets:
            return wb
        wb.close()
    except Exception:  # noqa: BLE001 — openpyxl leve des erreurs variees
        pass
    return None


def _load_wb(data: bytes):
    """Ouvre le classeur de façon robuste, en escaladant la tolérance :

    1. Mode `read_only` (streaming, rapide) — suffit pour la plupart des fichiers.
    2. Mode **normal** (`read_only=False`) — plus tolérant ; certains classeurs
       aux relations non standard ne remontent aucun onglet en streaming.
    3. **Normalisation LibreOffice** — dernier recours pour les fichiers
       « Strict Open XML Spreadsheet » ou exports exotiques qu'openpyxl ouvre
       sans erreur mais où il ne voit AUCUN onglet dans les deux modes : on les
       re-sauve en .xlsx standard via LibreOffice, puis on relit.

    Si tout échoue, on relance l'ouverture normale pour laisser remonter l'erreur
    (ou un classeur réellement vide) à l'appelant.
    """
    wb = _open_or_none(data, read_only=True)
    if wb is not None:
        return wb
    wb = _open_or_none(data, read_only=False)
    if wb is not None:
        return wb
    normalized = normalize_xlsx_bytes(data)
    if normalized:
        wb = _open_or_none(normalized, read_only=False)
        if wb is not None:
            return wb
    return load_workbook(io.BytesIO(data), read_only=False, data_only=True)


def list_sheets(data: bytes, sample_rows: int = _HEADER_SCAN, max_cols: int = 40) -> list[dict[str, Any]]:
    """Onglets de l'.xlsx : grille d'aperçu (rectangulaire), ligne d'en-tête
    (0-based) et `roles` = colonnes reconnues par nom d'en-tête (ou None).

    `roles` vient du MÊME détecteur que l'import auto (`_auto_columns_by_header`)
    pour que l'aperçu ouvre l'onglet et les colonnes que l'import retiendrait —
    sinon l'UI ouvre l'onglet 1 (souvent une page de garde) avec un mapping qui
    n'a aucun sens. Repli sur la ligne la plus large quand rien n'est reconnu.
    """
    wb = _load_wb(data)
    out: list[dict[str, Any]] = []
    try:
        for ws in wb.worksheets:
            grid: list[list[str]] = []
            for r in ws.iter_rows(min_row=1, max_row=sample_rows, values_only=True):
                grid.append([_norm(c) for c in list(r)[:max_cols]])
            ncols = max((len(r) for r in grid), default=0)
            grid = [r + [""] * (ncols - len(r)) for r in grid]  # rectangulaire
            detected = _auto_columns_by_header([tuple(r) for r in grid])
            header_row = detected[0] if detected else _detect_header_row(grid)
            out.append({
                "name": ws.title,
                "header_row": header_row,
                "rows": grid,
                "roles": detected[1] if detected else None,
            })
    finally:
        wb.close()
    return out


def _rules_from_rows(
    rows: list[tuple], columns: dict[str, int | None], header_idx: int,
    context_cols: list[int],
) -> list[ParsedRule]:
    """Transforme les lignes de données (après l'en-tête) en règles."""
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
        severity = _severity_from_cell(sev_cell) or _classify_severity(check)
        out.append(
            ParsedRule(
                label=(topic or "Règle importée")[:120],
                consigne=consigne[:2000],
                severity=severity,
            )
        )
    return out


# Longueur max d'une cellule d'en-tête : au-delà, c'est une ligne de données
# (phrase) qui contient par hasard un mot-clé (« vérification », « règle »…) et
# ne doit PAS être prise pour l'en-tête.
_HEADER_CELL_MAXLEN = 60


def _auto_columns_by_header(rows: list[tuple]) -> "tuple[int, dict, list[int]] | None":
    """Détection par nom d'en-tête (via `COLUMN_ALIASES`) : parmi les premières
    lignes, retient celle qui résout le PLUS DE RÔLES — et non la première venue
    contenant un « check ». Sans ce score, un titre de document
    (« CHECK-LIST QUALITE — REVUE ») capte le rôle « check » par sous-chaîne,
    devient l'en-tête, et la vraie en-tête placée plus bas se retrouve comptée
    comme une règle. À égalité, la ligne la plus haute gagne. Renvoie
    (header_idx, columns, context_cols) ou None si aucun en-tête reconnu."""
    best: tuple[int, dict[str, int]] | None = None
    for i, row in enumerate(rows[:_HEADER_SCAN]):
        cells = list(row)
        cand = _resolve_columns(cells)
        if "check" not in cand:
            continue
        # Un vrai en-tête est fait de libellés COURTS. Si la cellule « check » de
        # cette ligne est une longue phrase, c'est une ligne de données (qui
        # contient p.ex. le mot « vérification ») -> on ne la retient pas.
        if len(_cell(cells, cand["check"])) > _HEADER_CELL_MAXLEN:
            continue
        if best is None or len(cand) > len(best[1]):
            best = (i, dict(cand))
    if best is None:
        return None
    header_idx, columns = best
    ctx = [columns["context"]] if columns.get("context") is not None else []
    return header_idx, columns, ctx


def _auto_columns_heuristic(rows: list[tuple]) -> "tuple[int, dict, list[int]]":
    """Repli sans en-tête reconnu : la colonne « check » est celle au texte le
    plus long en moyenne (les vérifications sont des phrases) ; le « topic » est
    une colonne texte plus courte à sa gauche si elle existe. L'en-tête est la
    ligne la plus large."""
    grid = [[_norm(c) for c in list(r)] for r in rows[:_HEADER_SCAN]]
    header_idx = _detect_header_row(grid) if grid else 0
    data = rows[header_idx + 1:]
    ncols = max((len(list(r)) for r in data), default=0)
    if not data or ncols == 0:
        return header_idx, {"topic": 0, "check": 1}, []
    avg_len: list[float] = []
    for c in range(ncols):
        lengths = [len(_cell(list(r), c)) for r in data]
        nonzero = [n for n in lengths if n > 0]
        avg_len.append(sum(nonzero) / len(nonzero) if nonzero else 0.0)
    if max(avg_len) == 0:
        return header_idx, {"topic": 0, "check": 1}, []
    check_col = avg_len.index(max(avg_len))
    columns: dict[str, int | None] = {"check": check_col}
    if check_col != 0:
        columns["topic"] = 0
    return header_idx, columns, []


def parse_checklist(
    data: bytes, sheet: str | None = None, mapping: dict[str, Any] | None = None,
) -> list[ParsedRule]:
    """Construit les règles d'une checklist Excel.

    - **Mapping explicite** (`mapping.check` fourni par l'UI) : onglet `sheet`,
      colonnes imposées.
    - **Auto-détection** (sans mapping) : scanne TOUS les onglets (ou `sheet`
      seul s'il est précisé), détecte l'en-tête via `COLUMN_ALIASES`, et retient
      l'onglet qui produit le PLUS de règles. Si aucun en-tête n'est reconnu, un
      repli heuristique désigne la colonne « check » (texte le plus long).
    """
    wb = _load_wb(data)
    try:
        # --- Mode mapping explicite : un seul onglet, colonnes imposées -------
        if mapping and mapping.get("check") is not None:
            # `wb.active` peut valoir None (onglet actif non defini) -> repli 1er.
            ws = wb[sheet] if (sheet and sheet in wb.sheetnames) else wb.active
            if ws is None:
                ws = wb.worksheets[0] if wb.worksheets else None
            if ws is None:
                return []
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return []
            header_idx = int(mapping.get("header_row", 0))
            header_cells = list(rows[header_idx]) if 0 <= header_idx < len(rows) else []
            # topic/check sont imposés par l'utilisateur ; on détecte EN PLUS, par
            # nom d'en-tête, les rôles « prise en compte » et « sévérité » quand ils
            # ne sont pas mappés explicitement (parité word-reviewer).
            named = _resolve_columns(header_cells)

            def _role(key: str) -> int | None:
                v = mapping.get(key)
                return int(v) if v is not None else named.get(key)

            columns: dict[str, int | None] = {
                "topic": mapping.get("topic"),
                "check": int(mapping["check"]),
                "handling": _role("handling"),
                "severity": _role("severity"),
            }
            # « Zone » : rôle reconnu mais corpus-agent n'a pas de zone cible ->
            # on l'EXCLUT du texte de la règle (métadonnée, pas une consigne).
            zone_col = _role("zone")
            # Contexte : liste explicite si fournie (l'utilisateur désigne LA/LES
            # colonne(s) contexte), sinon TOUTE colonne sans rôle est ajoutée au
            # texte de la règle — comme word-reviewer. Cellules vides ignorées.
            explicit_ctx = [int(c) for c in (mapping.get("context") or [])]
            if explicit_ctx:
                context_cols = explicit_ctx
            else:
                special = {columns.get(k) for k in ("topic", "check", "handling", "severity")}
                special.add(zone_col)
                context_cols = [c for c in range(len(header_cells)) if c not in special]
            return _rules_from_rows(rows, columns, header_idx, context_cols)

        # --- Mode auto : on scanne tous les onglets et on garde le meilleur ---
        if sheet and sheet in wb.sheetnames:
            candidates = [wb[sheet]]
        else:
            candidates = list(wb.worksheets)

        best: list[ParsedRule] = []
        fallback_source: tuple | None = None  # onglet le plus « peuplé » pour l'heuristique
        for ws in candidates:
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            detected = _auto_columns_by_header(rows)
            if detected is not None:
                header_idx, columns, context_cols = detected
                rules = _rules_from_rows(rows, columns, header_idx, context_cols)
                if len(rules) > len(best):
                    best = rules
            # Mémorise l'onglet le plus rempli au cas où aucun en-tête ne matche.
            if fallback_source is None or len(rows) > len(fallback_source):
                fallback_source = rows

        # Aucun en-tête reconnu sur aucun onglet -> heuristique sur le plus rempli.
        if not best and fallback_source is not None:
            header_idx, columns, context_cols = _auto_columns_heuristic(fallback_source)
            best = _rules_from_rows(fallback_source, columns, header_idx, context_cols)
        return best
    finally:
        wb.close()
