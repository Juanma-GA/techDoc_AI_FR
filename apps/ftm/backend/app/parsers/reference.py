"""Lecture du référentiel unique d'un projet (1 classeur Excel).

Le référentiel contient typiquement les onglets « ATM » (suivi ATM FTM —
colonnes Excel BF/BH/BJ), « BASL » et « LCC ». Les checks v4 cross-checkent
le livrable FTM contre ce référentiel.

Fonctions pures, sans dépendance à la DB :
- `find_sheet(wb, *mots_cles)` : onglet dont le titre contient un mot-clé.
- `sheet_rows(path, *mots_cles)` : toutes les lignes d'un onglet (listes de str).
- `column_letter_values(path, lettre, *mots_cles)` : valeurs d'une colonne
  désignée par sa lettre Excel (ex. "BF").
- `sheet_names(path)` : titres des onglets du classeur.

Toute erreur de lecture (fichier absent, format non Excel, classeur corrompu)
renvoie une valeur vide — les checks à référence externe se skippent alors
silencieusement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter


def _open(path: Optional[str]) -> Optional[Any]:
    if not path:
        return None
    p = Path(path)
    if not p.is_file() or p.suffix.lower() not in (".xlsx", ".xlsm"):
        return None
    try:
        return load_workbook(path, data_only=True, read_only=True)
    except Exception:  # noqa: BLE001
        return None


def find_sheet(wb: Any, *keywords: str) -> Optional[Any]:
    """Premier onglet dont le titre contient (insensible à la casse) l'un des
    mots-clés. Sans mot-clé, renvoie le premier onglet."""
    if wb is None or not wb.worksheets:
        return None
    if not keywords:
        return wb.worksheets[0]
    kws = [k.lower() for k in keywords if k]
    for ws in wb.worksheets:
        title = (ws.title or "").lower()
        if any(k in title for k in kws):
            return ws
    return None


def sheet_names(path: Optional[str]) -> list[str]:
    wb = _open(path)
    return [ws.title for ws in wb.worksheets] if wb is not None else []


def _find_sheet_exact(wb: Any, sheet_title: str) -> Optional[Any]:
    """Onglet dont le titre est EXACTEMENT `sheet_title` (sélection par menu)."""
    if wb is None or not sheet_title:
        return None
    for ws in wb.worksheets:
        if (ws.title or "") == sheet_title:
            return ws
    return None


_HEADER_SCAN_ROWS = 25


def _detect_header_row(scanned: list[tuple[Any, ...]]) -> int:
    """Indice (0-based) de la ligne d'en-tête parmi les lignes scannées.

    Heuristique : la ligne d'en-tête est la **première ligne la plus large**
    (nombre maximal de cellules non vides). Les lignes de titre au-dessus sont
    étroites (souvent fusionnées → 1 cellule) ; les lignes de données sous
    l'en-tête comportent des trous → l'en-tête, qui nomme chaque colonne, est
    en général la plus remplie, et la première de cette largeur."""
    def _filled(row: tuple[Any, ...]) -> int:
        return sum(1 for c in row if c is not None and str(c).strip())

    counts = [_filled(r) for r in scanned]
    if not counts or max(counts) == 0:
        return 0
    return counts.index(max(counts))


def sheet_columns(path: Optional[str], sheet_title: str) -> list[dict[str, str]]:
    """Colonnes d'un onglet : `[{"letter","header"}]`. La ligne d'en-tête est
    **détectée** (pas forcément la 1re ligne — cf. `_detect_header_row`), ce qui
    gère les onglets avec lignes de titre. Alimente les menus « Colonne »."""
    wb = _open(path)
    ws = _find_sheet_exact(wb, sheet_title)
    if ws is None:
        return []
    scanned: list[tuple[Any, ...]] = []
    for row in ws.iter_rows(min_row=1, max_row=_HEADER_SCAN_ROWS, values_only=True):
        scanned.append(row or ())
    if not scanned:
        return []
    header_row = scanned[_detect_header_row(scanned)]
    # Largeur = colonne la plus à droite vue sur tout le scan (les lignes de
    # données peuvent dépasser la ligne d'en-tête).
    max_cols = max((len(r) for r in scanned), default=0)
    out: list[dict[str, str]] = []
    for i in range(1, max_cols + 1):
        val = header_row[i - 1] if i - 1 < len(header_row) else None
        out.append({
            "letter": get_column_letter(i),
            "header": "" if val is None else str(val).strip(),
        })
    return out


def column_values_for_sheet(
    path: Optional[str], sheet_title: str, column_letter: str
) -> list[str]:
    """Valeurs non vides (uniques, ordre préservé) d'une colonne d'un onglet
    désigné par son titre exact."""
    wb = _open(path)
    ws = _find_sheet_exact(wb, sheet_title)
    if ws is None:
        return []
    try:
        idx = column_index_from_string((column_letter or "").strip().upper())
    except (ValueError, AttributeError):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for row in ws.iter_rows(min_col=idx, max_col=idx, values_only=True):
        val = row[0] if row else None
        if val is None:
            continue
        s = str(val).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def rows_with_letters_for_sheet(
    path: Optional[str], sheet_title: str, letters: tuple[str, ...]
) -> list[dict[str, str]]:
    """Comme `rows_with_letters` mais l'onglet est désigné par son titre
    exact (sélectionné via menu déroulant)."""
    wb = _open(path)
    ws = _find_sheet_exact(wb, sheet_title)
    if ws is None:
        return []
    idxs: dict[str, int] = {}
    for letter in letters:
        try:
            idxs[letter] = column_index_from_string((letter or "").strip().upper())
        except (ValueError, AttributeError):
            continue
    if not idxs:
        return []
    max_idx = max(idxs.values())
    out: list[dict[str, str]] = []
    for row in ws.iter_rows(min_col=1, max_col=max_idx, values_only=True):
        d: dict[str, str] = {}
        for letter, ci in idxs.items():
            val = row[ci - 1] if ci - 1 < len(row) else None
            d[letter] = "" if val is None else str(val).strip()
        if any(d.values()):
            out.append(d)
    return out


def reference_column_values(
    path: Optional[str],
    sheet_title: str,
    column_letter: str,
    fallback_keywords: tuple[str, ...] = (),
) -> list[str]:
    """Valeurs d'une colonne de référence. Onglet exact si `sheet_title` est
    renseigné ; sinon recherche par mots-clés (compat. ascendante : projet
    sans mapping explicite)."""
    if sheet_title:
        return column_values_for_sheet(path, sheet_title, column_letter)
    return column_letter_values(path, column_letter, *fallback_keywords)


def sheet_rows(path: Optional[str], *keywords: str) -> list[list[str]]:
    """Toutes les lignes de l'onglet identifié par les mots-clés, chaque
    cellule normalisée en `str` strippé ('' si vide)."""
    wb = _open(path)
    if wb is None:
        return []
    ws = find_sheet(wb, *keywords)
    if ws is None:
        return []
    return [
        ["" if c is None else str(c).strip() for c in row]
        for row in ws.iter_rows(values_only=True)
    ]


def rows_by_letter(
    path: Optional[str], sheet_keywords: tuple[str, ...],
) -> list[dict[str, str]]:
    """Toutes les rows de l'onglet identifié, chaque cellule keyée par sa
    lettre Excel (A, B, …, AA, …, BD, …). Utile pour les règles qui spécifient
    une colonne par lettre (« en colonne AY », « en colonnes BB et BD »).

    Lignes entièrement vides ignorées. Renvoie `[]` si le fichier n'est pas
    un xlsx/xlsm, si le path est absent, ou si l'onglet n'est pas trouvé.
    """
    wb = _open(path)
    if wb is None:
        return []
    ws = find_sheet(wb, *sheet_keywords)
    if ws is None:
        return []
    out: list[dict[str, str]] = []
    for row in ws.iter_rows(values_only=True):
        d: dict[str, str] = {}
        for i, val in enumerate(row):
            letter = get_column_letter(i + 1)
            d[letter] = "" if val is None else str(val).strip()
        if any(d.values()):
            out.append(d)
    return out


def rows_with_letters(
    path: Optional[str], sheet_keywords: tuple[str, ...], letters: tuple[str, ...]
) -> list[dict[str, str]]:
    """Pour chaque ligne de l'onglet identifié, un dict `{lettre: valeur}`
    aligné sur les colonnes Excel demandées (ex. BF/BH/BJ row-aligned).
    Les lignes entièrement vides sur ces colonnes sont écartées."""
    wb = _open(path)
    if wb is None:
        return []
    ws = find_sheet(wb, *sheet_keywords)
    if ws is None:
        return []
    idxs: dict[str, int] = {}
    for letter in letters:
        try:
            idxs[letter] = column_index_from_string((letter or "").strip().upper())
        except (ValueError, AttributeError):
            continue
    if not idxs:
        return []
    max_idx = max(idxs.values())
    out: list[dict[str, str]] = []
    for row in ws.iter_rows(min_col=1, max_col=max_idx, values_only=True):
        d: dict[str, str] = {}
        for letter, ci in idxs.items():
            val = row[ci - 1] if ci - 1 < len(row) else None
            d[letter] = "" if val is None else str(val).strip()
        if any(d.values()):
            out.append(d)
    return out


def column_letter_values(
    path: Optional[str], column_letter: str, *sheet_keywords: str
) -> list[str]:
    """Valeurs non vides (uniques, ordre d'apparition préservé) de la colonne
    désignée par sa lettre Excel (ex. "BF", "BH", "BJ") dans l'onglet
    correspondant aux mots-clés."""
    wb = _open(path)
    if wb is None:
        return []
    ws = find_sheet(wb, *sheet_keywords)
    if ws is None:
        return []
    try:
        idx = column_index_from_string((column_letter or "").strip().upper())
    except (ValueError, AttributeError):
        return []

    seen: set[str] = set()
    out: list[str] = []
    for row in ws.iter_rows(min_col=idx, max_col=idx, values_only=True):
        val = row[0] if row else None
        if val is None:
            continue
        s = str(val).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out
