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
HEADER_KEYS: dict[str, tuple[str, ...]] = {
    "catpart": ("catpart", "cat part", "nom fichier", "fichier", "part number", "reference", "piece"),
    "designation": ("designation", "libelle", "description"),
    "sin": ("sin",),
    "version": ("version", "indice", "evolution"),
    "to_treat": ("a traiter", "traiter", "modifie", "modification", "maj", "statut", "status", "evolue"),
    "color": ("couleur", "color", "rvb", "rgb"),
}

_TRUE_TOKENS = {"x", "oui", "yes", "y", "1", "true", "vrai", "a traiter", "traiter", "modifie", "maj", "ok"}

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


def _is_true(val: object) -> bool:
    return _norm(val) in _TRUE_TOKENS


def _detect_header(rows: list[list], max_scan: int = 20) -> tuple[int, dict[str, int]]:
    """Trouve la ligne d'en-tete (celle qui mappe le plus de champs)."""
    best_row, best_map = -1, {}
    for i, row in enumerate(rows[:max_scan]):
        mapping: dict[str, int] = {}
        for col, cell in enumerate(row):
            field = _match_field(cell)
            if field and field not in mapping:
                mapping[field] = col
        if len(mapping) > len(best_map):
            best_row, best_map = i, mapping
    return best_row, best_map


def parse_nomenclature(path: str, sheet: Optional[str] = None) -> dict:
    """Parse la nomenclature -> {sheet, columns, items[], summary}.

    `items` : liste de dict {catpart, designation, sin, version, to_treat,
    mono_color, color_r/g/b, source_row}.
    """
    try:
        wb = load_workbook(filename=path, read_only=True, data_only=True, keep_vba=False)
    except Exception as e:  # noqa: BLE001 - openpyxl leve des erreurs variees
        raise AppError(
            "NOMENCLATURE_READ_FAILED",
            f"Lecture du fichier nomenclature impossible : {type(e).__name__}",
            status_code=400,
        ) from e

    try:
        ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb[wb.sheetnames[0]]
        rows: list[list] = []
        for r in ws.iter_rows(values_only=True):
            rows.append(list(r))
            if len(rows) >= _MAX_ROWS:
                break
    finally:
        wb.close()

    header_idx, colmap = _detect_header(rows)
    if header_idx < 0 or "catpart" not in colmap:
        raise AppError(
            "NOMENCLATURE_NO_HEADER",
            "En-tete introuvable (aucune colonne CATPart detectee). "
            "Verifiez la feuille ou ajustez les mots-cles d'en-tete.",
            status_code=400,
            detail={"detected_columns": list(colmap.keys())},
        )

    def _cell(row: list, field: str) -> object:
        idx = colmap.get(field)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    items: list[dict] = []
    for ridx in range(header_idx + 1, len(rows)):
        row = rows[ridx]
        catpart = _cell(row, "catpart")
        if catpart is None or not str(catpart).strip():
            continue
        color = parse_color(_cell(row, "color"))
        items.append(
            {
                "catpart": str(catpart).strip()[:500],
                "designation": str(_cell(row, "designation") or "").strip(),
                "sin": str(_cell(row, "sin") or "").strip()[:200],
                "version": str(_cell(row, "version") or "").strip()[:60],
                "to_treat": _is_true(_cell(row, "to_treat")) if "to_treat" in colmap else False,
                "mono_color": color is not None,
                "color_r": color[0] if color else 0,
                "color_g": color[1] if color else 0,
                "color_b": color[2] if color else 0,
                "source_row": ridx + 1,  # 1-based comme Excel
            }
        )

    summary = {
        "rows": len(items),
        "to_treat": sum(1 for it in items if it["to_treat"]),
        "mono_color": sum(1 for it in items if it["mono_color"]),
        "detected_columns": sorted(colmap.keys()),
        "header_row": header_idx + 1,
    }
    return {"sheet": ws.title, "columns": sorted(colmap.keys()), "items": items, "summary": summary}


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
