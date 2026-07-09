"""Detection d'en-tete + mapping de colonnes pour la nomenclature CATI.

Porte la logique tolerante de `catia-toolbox/core/nomenclature.py` (`_norm`,
match par mots-cles, detection de la ligne d'en-tete) et l'adapte aux libelles
d'un BOM CATI (FIG REP / DESIGNATION / SYMBOLE / IDENTIFICATION{Code,Reference}
/ QUANTITE{ES,EM} / APP).

Utilise par le chemin d'extraction "table structuree" (`page.find_tables`) de
`pdf_table.py`. L'en-tete CATI est multi-lignes : on concatene le texte de
plusieurs lignes d'en-tete par colonne avant de matcher.
"""

from __future__ import annotations

import unicodedata
from typing import Any

# Mot-cle d'en-tete (normalise) -> champ logique. Premier match gagne.
# L'ordre compte : "reference" avant "rep" pour ne pas confondre Reference/FIG REP.
HEADER_KEYS: dict[str, tuple[str, ...]] = {
    "fig": ("fig rep", "fig/rep", "figrep", "fig", "repere", "rep"),
    "designation": ("designation", "libelle", "description", "denomination"),
    "symbole": ("symbole", "symbol"),
    "code": ("code",),
    "reference": ("reference", "ref"),
    "qty": ("quantite", "quantity", "qte", "qty"),
    "app": ("app",),
}

# Roles de la colonne "Code" d'un CATI (identifient les 3 sous-lignes d'un article).
ROLE_TOKENS: dict[str, str] = {
    "client": "ref_client",
    "interne": "ref_interne",
    "fournisseur": "ref_fournisseur",
}


def norm(s: object) -> str:
    """Minuscule, sans accents, espaces compresses."""
    txt = "" if s is None else str(s)
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")
    return " ".join(txt.lower().split())


def match_field(header: str) -> str | None:
    """Retourne le champ logique correspondant a un libelle d'en-tete, ou None."""
    h = norm(header)
    if not h:
        return None
    for field, keys in HEADER_KEYS.items():
        if any(k in h for k in keys):
            return field
    return None


def role_of(value: object) -> str | None:
    """Mappe une valeur de colonne 'Code' (Client/Interne/Fournisseur) -> champ ref."""
    v = norm(value)
    for token, field in ROLE_TOKENS.items():
        if token in v:
            return field
    return None


def detect_header(rows: list[list[Any]], max_scan: int = 8) -> tuple[int, dict[str, int]]:
    """Trouve la ligne d'en-tete (celle qui mappe le plus de champs).

    Combine chaque ligne candidate avec la suivante (en-tete CATI multi-lignes :
    'IDENTIFICATION' au-dessus de 'Code'/'Reference') pour maximiser les matches.
    Renvoie (index_ligne_0based, {champ: index_colonne_0based}). (-1, {}) si rien.
    """
    best_row: int = -1
    best_map: dict[str, int] = {}
    scan = rows[:max_scan]
    for i, row in enumerate(scan):
        combined = list(row)
        # Fusionne le libelle de la ligne suivante (sous-en-tetes Code/Ref/ES/EM).
        if i + 1 < len(scan):
            nxt = scan[i + 1]
            for c in range(max(len(combined), len(nxt))):
                a = combined[c] if c < len(combined) else ""
                b = nxt[c] if c < len(nxt) else ""
                combined_c = f"{a or ''} {b or ''}".strip()
                if c < len(combined):
                    combined[c] = combined_c
                else:
                    combined.append(combined_c)
        mapping: dict[str, int] = {}
        for col, cell in enumerate(combined):
            field = match_field(cell)
            if field and field not in mapping:
                mapping[field] = col
        if len(mapping) > len(best_map):
            best_row, best_map = i, mapping
    return best_row, best_map
