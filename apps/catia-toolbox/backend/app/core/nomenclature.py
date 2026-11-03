"""Etape 1 - Identification CATPart a traiter (nomenclature .xlsm + DE .zip).

Lit le fichier nomenclature Excel (.xlsm / .xlsx) avec openpyxl (valeurs
uniquement, pas les macros). Detecte la ligne d'en-tete et mappe les colonnes
par mots-cles tolerants. Produit une liste de pieces : CATPart, designation,
SIN, version, drapeau "a traiter", couleur (mono) quand l'info est presente.

Les libelles d'en-tete exacts varient selon le fichier reel -> les ensembles
de mots-cles `HEADER_KEYS` sont ajustables. Lit aussi le contenu d'un .zip de
donnees d'entree (DE) en metadonnees seules (noms / tailles, jamais extrait).
"""

from __future__ import annotations

import unicodedata
import zipfile
from typing import Optional

from openpyxl import load_workbook

from app.core.errors import AppError


# Mot-cle d'en-tete (normalise) -> champ logique. Premier match gagne.
# NB: l'ordre compte (premier match) — les cles specifiques (old/new pn, ref
# couleur) sont placees AVANT les cles generiques (catpart, color) pour ne pas
# etre capturees par elles.
HEADER_KEYS: dict[str, tuple[str, ...]] = {
    "old_pn": ("old pn", "old p/n", "ancien pn", "ancien p/n", "ancienne ref", "pn ancien"),
    "new_pn": ("new pn", "new p/n", "nouveau pn", "nouveau p/n", "nouvelle ref", "pn nouveau"),
    "old_rev": ("old rev", "ancien indice", "ancienne rev", "rev ancien"),
    "new_rev": ("new rev", "nouvel indice", "nouvelle rev", "rev nouveau"),
    "replaced": ("piece remplacee", "remplacee", "remplacement", "replaced"),
    "color_ref": ("ref couleur", "reference couleur", "ref color"),
    "materials": ("materiaux", "materiau", "matiere", "matiere premiere", "material"),
    "designation": ("designation", "libelle", "description"),
    "sin": ("sin",),
    "version": ("version", "indice", "evolution"),
    "to_treat": ("a traiter", "traiter", "modifie", "modification", "maj", "statut", "status", "evolue"),
    "optimized": ("x000", "pieces optimisees", "piece optimisee"),
    "color": ("couleur", "color", "rvb", "rgb"),
    "catpart": ("catpart", "cat part", "nom fichier", "fichier", "part number", "reference", "piece"),
}

# Couleurs nommees frequentes -> RGB (table minimale, ajustable).
_NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "noir": (0, 0, 0), "black": (0, 0, 0),
    "blanc": (255, 255, 255), "white": (255, 255, 255),
    "rouge": (255, 0, 0), "red": (255, 0, 0),
    "vert": (0, 128, 0), "green": (0, 128, 0),
    "bleu": (0, 0, 255), "blue": (0, 0, 255),
    "jaune": (255, 255, 0), "yellow": (255, 255, 0),
    "gris": (128, 128, 128), "gray": (128, 128, 128), "grey": (128, 128, 128),
    "orange": (255, 165, 0),
}

_MAX_ROWS = 100000


def _norm(s: object) -> str:
    """Minuscule, sans accents, espaces compresses."""
    txt = "" if s is None else str(s)
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")
    return " ".join(txt.lower().split())


def _match_field(header: str) -> Optional[str]:
    h = _norm(header)
    if not h:
        return None
    for field, keys in HEADER_KEYS.items():
        if any(k in h for k in keys):
            return field
    return None


def parse_color(val: object) -> Optional[tuple[int, int, int]]:
    """Parse une couleur : 'r,g,b' / 'r;g;b' / '#rrggbb' / nom connu."""
    s = _norm(val)
    if not s:
        return None
    if s in _NAMED_COLORS:
        return _NAMED_COLORS[s]
    raw = str(val).strip()
    if raw.startswith("#") and len(raw) == 7:
        try:
            return (int(raw[1:3], 16), int(raw[3:5], 16), int(raw[5:7], 16))
        except ValueError:
            return None
    for sep in (",", ";", "/"):
        if sep in raw:
            parts = [p.strip() for p in raw.split(sep)]
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                vals = [max(0, min(255, int(p))) for p in parts]
                return (vals[0], vals[1], vals[2])
    return None


def _detect_header(rows: list[list], max_scan: int = 20) -> tuple[int, dict[str, int]]:
    """Trouve la ligne d'en-tete (celle qui mappe le plus de champs)."""
    best_row, best_map = -1, {}
    for i, row in enumerate(rows[:max_scan]):
        mapping: dict[str, int] = {}
        for col, cell in enumerate(row):
            field = _match_field(cell)
            exact_sin = (
                field == "sin"
                and _norm(cell) == "sin"
                and ("sin" not in mapping or _norm(row[mapping["sin"]]) != "sin")
            )
            if field and (field not in mapping or exact_sin):
                mapping[field] = col
        if len(mapping) > len(best_map):
            best_row, best_map = i, mapping
    return best_row, best_map


def _load(path: str):
    try:
        return load_workbook(filename=path, read_only=True, data_only=True, keep_vba=False)
    except Exception as e:  # noqa: BLE001 - openpyxl leve des erreurs variees
        raise AppError(
            "NOMENCLATURE_READ_FAILED",
            f"Lecture du fichier nomenclature impossible : {type(e).__name__}",
            status_code=400,
        ) from e


def list_sheets(path: str) -> list[str]:
    """Liste les onglets (feuilles) du classeur."""
    wb = _load(path)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def preview_sheet(path: str, sheet: Optional[str] = None, rows: int = 15) -> dict:
    """Apercu des `rows` premieres lignes d'un onglet (facon corpus / FTM).

    Renvoie {sheets, sheet, header_row_detected (1-based), columns_detected, rows}.
    `rows` est une grille de chaines (cellules vides -> "").
    """
    wb = _load(path)
    try:
        sheets = list(wb.sheetnames)
        title = sheet if (sheet and sheet in sheets) else sheets[0]
        ws = wb[title]
        scanned: list[list] = []
        scan_cap = max(int(rows or 15), 25)  # assez de lignes pour detecter l'en-tete
        for r in ws.iter_rows(values_only=True):
            scanned.append(list(r))
            if len(scanned) >= scan_cap:
                break
        title = ws.title
    finally:
        wb.close()

    header_idx, colmap = _detect_header(scanned)
    n = max(1, min(int(rows or 15), len(scanned)))
    view = scanned[:n]
    max_cols = max((len(r) for r in view), default=0)
    grid = [
        ["" if (i >= len(r) or r[i] is None) else str(r[i]).strip() for i in range(max_cols)]
        for r in view
    ]
    return {
        "sheets": sheets,
        "sheet": title,
        "header_row_detected": header_idx + 1 if header_idx >= 0 else 0,
        "columns_detected": sorted(colmap.keys()),
        "columns_map": dict(colmap),  # champ -> index colonne (0-based) detecte
        "rows": grid,
    }


_FIELDS = (
    "catpart", "designation", "sin", "version", "to_treat", "optimized", "color",
    "old_pn", "new_pn", "old_rev", "new_rev", "replaced", "color_ref", "materials",
)

# Champs d'identite utilisables pour relier une ligne "slots" (onglet Materiaux)
# a une piece de la nomenclature.
IDENTITY_FIELDS = ("catpart", "sin", "old_pn", "new_pn")


def _is_mono_body(slots: list[str]) -> bool:
    """Piece mono-corps : un seul slot renseigne OU tous les slots renseignes
    identiques (une seule valeur distincte parmi les n slots). Aucun slot
    renseigne => pas mono-corps."""
    filled = [s for s in slots if s]
    return len(set(filled)) == 1

# Colonnes qui suffisent, seules ou combinees, a identifier une piece.
_IDENTITY_FIELDS = ("catpart", "sin", "old_pn", "new_pn")


def _resolve_columns(rows: list[list], mapping: Optional[dict]) -> tuple[int, dict[str, int]]:
    """En-tete + colonnes : mapping manuel fourni, sinon detection auto.

    L'identite peut passer par CATPart *ou* SIN *ou* PN (old/new) : aucune de
    ces colonnes n'est individuellement obligatoire, mais au moins une doit
    exister.
    """
    if mapping:
        header_idx = int(mapping.get("header_row") or 0) - 1
        if header_idx < 0:
            raise AppError("MAPPING_INVALID", "header_row doit etre >= 1.", status_code=400)
        colmap = {f: int(mapping[f]) for f in _FIELDS if mapping.get(f) is not None}
        if not any(f in colmap for f in _IDENTITY_FIELDS):
            raise AppError(
                "MAPPING_NO_IDENTITY",
                "Mappez au moins une colonne d'identite : SIN, OLD P/N ou NEW P/N (ou CATPart).",
                status_code=400,
            )
        return header_idx, colmap

    header_idx, colmap = _detect_header(rows)
    if header_idx < 0 or not any(f in colmap for f in _IDENTITY_FIELDS):
        raise AppError(
            "NOMENCLATURE_NO_HEADER",
            "En-tete introuvable (aucune colonne d'identite SIN / PN / CATPart detectee). "
            "Configurez le mapping (ligne d'en-tete + colonnes) ou ajustez les mots-cles.",
            status_code=400,
            detail={"detected_columns": list(colmap.keys())},
        )
    return header_idx, colmap


def _build_items(rows: list[list], header_idx: int, colmap: dict[str, int]) -> list[dict]:
    def _cell(row: list, field: str) -> object:
        idx = colmap.get(field)
        if idx is None or idx < 0 or idx >= len(row):
            return None
        return row[idx]

    def _text(v: object) -> str:
        return "" if v is None else str(v).strip()

    items: list[dict] = []
    for ridx in range(header_idx + 1, len(rows)):
        row = rows[ridx]
        catpart = _text(_cell(row, "catpart"))[:500]
        sin = _text(_cell(row, "sin"))[:200]
        designation = _text(_cell(row, "designation"))
        version = _text(_cell(row, "version"))[:60]
        old_pn = _text(_cell(row, "old_pn"))[:500]
        new_pn = _text(_cell(row, "new_pn"))[:500]
        old_rev = _text(_cell(row, "old_rev"))[:60]
        new_rev = _text(_cell(row, "new_rev"))[:60]
        color_ref = _text(_cell(row, "color_ref"))[:200]
        materials = _text(_cell(row, "materials"))[:200]
        to_treat_raw = _text(_cell(row, "to_treat"))
        optimized_raw = _text(_cell(row, "optimized"))
        color = parse_color(_cell(row, "color"))
        # On prend TOUTES les lignes des colonnes mappees : on n'ignore qu'une
        # ligne entierement vide (aucune cellule mappee renseignee).
        if not any(
            [catpart, sin, designation, version, old_pn, new_pn, old_rev, new_rev,
             color_ref, materials, to_treat_raw, optimized_raw, color]
        ):
            continue
        # "A traiter" = cellule "A TRAITER" NON VIDE (seul filtre attendu), quel
        # que soit son contenu -- pas de liste de valeurs "vraies".
        to_treat = ("to_treat" in colmap) and bool(to_treat_raw)
        optimized = ("optimized" in colmap) and _norm(optimized_raw) == "x"
        # "Piece remplacee" : colonne dediee non vide OU ancien/nouveau PN differents.
        replaced_flag = ("replaced" in colmap) and bool(_text(_cell(row, "replaced")))
        replaced = replaced_flag or bool(old_pn and new_pn and old_pn != new_pn)
        items.append(
            {
                "catpart": catpart,
                "designation": designation,
                "sin": sin,
                "version": version,
                "to_treat": to_treat,
                "to_treat_value": to_treat_raw,
                "optimized": optimized,
                "replaced": replaced,
                "old_pn": old_pn,
                "new_pn": new_pn,
                "old_rev": old_rev,
                "new_rev": new_rev,
                "color_ref": color_ref,
                "materials": materials,
                "mono_color": color is not None,
                "color_r": color[0] if color else 0,
                "color_g": color[1] if color else 0,
                "color_b": color[2] if color else 0,
                "source_row": ridx + 1,  # 1-based comme Excel
            }
        )
    return items


def parse_nomenclature(path: str, sheet: Optional[str] = None, mapping: Optional[dict] = None) -> dict:
    """Parse la nomenclature -> {sheet, columns, items[], summary}.

    `mapping` (optionnel) : {header_row (1-based), catpart, designation, sin,
    version, to_treat, color} ou chaque champ est un index de colonne 0-based.
    Quand fourni, court-circuite la detection automatique.
    """
    wb = _load(path)
    try:
        ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb[wb.sheetnames[0]]
        title = ws.title
        rows: list[list] = []
        for r in ws.iter_rows(values_only=True):
            rows.append(list(r))
            if len(rows) >= _MAX_ROWS:
                break
    finally:
        wb.close()

    header_idx, colmap = _resolve_columns(rows, mapping)
    items = _build_items(rows, header_idx, colmap)

    summary = {
        "rows": len(items),
        "to_treat": sum(1 for it in items if it["to_treat"]),
        "optimized": sum(1 for it in items if it["optimized"]),
        "replaced": sum(1 for it in items if it["replaced"]),
        "mono_body": 0,  # renseigne apres l'etape Mono-Corps (onglet Materiaux)
        "mono_color": sum(1 for it in items if it["mono_color"]),
        "detected_columns": sorted(colmap.keys()),
        "header_row": header_idx + 1,
        "manual_mapping": mapping is not None,
    }
    return {"sheet": title, "columns": sorted(colmap.keys()), "items": items, "summary": summary}


def parse_mono_corps(
    path: str,
    sheet: Optional[str],
    header_row: int,
    identity_col: int,
    slot_cols: Optional[list[int]] = None,
    first_slot_col: Optional[int] = None,
) -> dict:
    """Parse l'onglet Materiaux : mono_body par valeur d'identite.

    Pour chaque ligne (a partir de `header_row`, 1-based), lit la colonne
    d'identite (`identity_col`, 0-based). Les colonnes slots sont determinees,
    par ordre de priorite :
      1. `slot_cols` (0-based) si fourni explicitement ;
      2. sinon, a partir de `first_slot_col` (0-based) jusqu'a la derniere
         colonne de l'onglet (la 1re colonne Slot comparee a toutes les
         suivantes), l'identite exclue ;
      3. sinon, TOUTES les colonnes sauf l'identite.
    mono_body = une seule valeur distincte parmi les slots renseignes.
    L'appariement avec les pieces se fait cote appelant (via l'identite choisie).

    Retour : {map: {identity_value: mono_body}, items, rows, mono, slot_cols}.
    """
    wb = _load(path)
    try:
        ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb[wb.sheetnames[0]]
        rows: list[list] = []
        for r in ws.iter_rows(values_only=True):
            rows.append(list(r))
            if len(rows) >= _MAX_ROWS:
                break
    finally:
        wb.close()

    # Colonnes slots : explicites, sinon depuis `first_slot_col` jusqu'a la fin,
    # sinon toutes les colonnes sauf l'identite.
    if slot_cols:
        cols = list(slot_cols)
    else:
        max_cols = max((len(r) for r in rows), default=0)
        start = first_slot_col if first_slot_col is not None else 0
        cols = [c for c in range(start, max_cols) if c != identity_col]

    def _at(row: list, col: int) -> str:
        return "" if (col < 0 or col >= len(row) or row[col] is None) else str(row[col]).strip()

    result: dict[str, bool] = {}
    items: list[dict] = []
    for ridx in range(header_row, len(rows)):  # header_row (1-based) = 1re ligne de donnees (0-based)
        row = rows[ridx]
        ident = _at(row, identity_col)[:500]
        slots = [_at(row, c)[:200] for c in cols]
        if not ident and not any(slots):
            continue  # ligne entierement vide
        mono = _is_mono_body(slots)
        items.append({"identity": ident, "slots": slots, "mono_body": mono})
        if ident:
            result[ident] = mono  # derniere ligne gagnante si identite dupliquee
    return {
        "map": result,
        "items": items,
        "rows": len(items),
        "mono": sum(1 for it in items if it["mono_body"]),
        "slot_cols": cols,
    }


def list_zip(path: str, max_entries: int = 50000) -> list[dict]:
    """Liste le contenu d'un .zip (DE) en metadonnees seules. N'extrait rien."""
    try:
        with zipfile.ZipFile(path) as zf:
            out: list[dict] = []
            for info in zf.infolist():
                out.append(
                    {
                        "name": info.filename,
                        "size": int(info.file_size),
                        "is_dir": info.is_dir(),
                    }
                )
                if len(out) >= max_entries:
                    break
            return out
    except zipfile.BadZipFile as e:
        raise AppError("ZIP_INVALID", "Fichier .zip invalide ou corrompu.", status_code=400) from e
