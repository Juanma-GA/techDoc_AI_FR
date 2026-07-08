"""Schema structurel de la feuille `Catalogue` du template Excel CATI.

Source de verite unique pour :
  - les 21 colonnes techniques (A -> U) et leur cle metier,
  - le mapping "champ d'article extrait" -> colonne Excel,
  - le mapping "metadonnee document (header_meta)" -> colonne Excel,
  - la construction d'une ligne Excel (par article) et du bloc en-tete module.

Rappel (valide avec l'utilisateur) : le PDF et l'Excel fournis ne sont PAS un
couple entree/sortie coherent. Le mapping ci-dessous est *structurel* : quel
champ va dans quelle colonne. On ne code jamais en dur les valeurs de l'exemple
(F1888, C4546, ...). Les constantes document-level viennent de `header_meta`.
"""

from __future__ import annotations

from typing import Any

# Colonnes de la feuille Catalogue, dans l'ordre A..U (cle technique = ligne 1).
CATALOGUE_COLUMNS: tuple[str, ...] = (
    "module",           # A
    "partid",           # B
    "fig",              # C
    "figreflink",       # D
    "aplomb",           # E
    "description",      # F
    "matiere",          # G
    "reperecircuit",    # H
    "modulereference",  # I
    "bt001_part_no",    # J
    "sncf_partno",      # K
    "pn_supplier",      # L
    "otan_supplier",    # M
    "qty_assy",         # N
    "app_nom",          # O
    "app_from",         # P
    "app_to",           # Q
    "symbole_sncf",     # R
    "code_pbs",         # S
    "drw",              # T
    "nposte",           # U
)

# Champ logique d'un article extrait du PDF -> cle de colonne Catalogue.
# (le reste des colonnes vient de header_meta ou reste vide)
ITEM_FIELD_TO_COLUMN: dict[str, str] = {
    "fig": "fig",                       # FIG REP (ex. 10A) -> C
    "figreflink": "figreflink",         # partie numerique (10A -> 10) -> D
    "aplomb": "aplomb",                 # points d'indentation de la designation -> E
    "description": "description",       # DESIGNATION sans les points -> F
    "matiere": "matiere",               # colonne matiere si presente -> G
    "ref_interne": "bt001_part_no",     # reference Interne (I....) -> J
    "ref_client": "sncf_partno",        # reference Client (C....) -> K
    "ref_fournisseur": "pn_supplier",   # reference Fournisseur (F....) -> L
    "qty": "qty_assy",                  # QUANTITE (ES) -> N
    "symbole": "symbole_sncf",          # colonne SYMBOLE -> R
}

# Cles de header_meta (metadonnees document saisies dans l'UI) -> valeur repetee
# sur chaque ligne d'article. `module` (A) et `otan_supplier` (M) sont constants
# pour tout le document.
HEADER_META_KEYS: tuple[str, ...] = (
    "module",         # A : code module / plan (ex. F1888-PL001A)
    "otan_supplier",  # M : nom fournisseur (ex. NOM FRN)
    "drw",            # T : nom de fichier illustration (ex. F1888.png)
    "top_assembly",   # fig du bloc en-tete module (ex. +1A)
    "bom_title",      # description du bloc en-tete module (titre du BOM)
)


def blank_row() -> dict[str, Any]:
    """Ligne Catalogue vide (toutes colonnes -> None)."""
    return {col: None for col in CATALOGUE_COLUMNS}


def item_to_row(
    item: dict[str, Any],
    header_meta: dict[str, Any] | None = None,
    excel_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Projette un article extrait + metadonnees document sur une ligne Catalogue.

    `item` : champs logiques (fig, figreflink, aplomb, description, matiere,
    ref_interne, ref_client, ref_fournisseur, qty, symbole).
    `header_meta` : constantes document (module, otan_supplier, ...).
    `excel_map` (profil) : override {champ_article: cle_colonne_excel} par-dessus
    ITEM_FIELD_TO_COLUMN.
    """
    meta = header_meta or {}
    mapping = {**ITEM_FIELD_TO_COLUMN, **(excel_map or {})}
    row = blank_row()

    for field, col in mapping.items():
        if col not in row:
            continue  # cle de colonne inconnue -> ignoree
        val = item.get(field)
        if val is not None and str(val).strip() != "":
            row[col] = val

    # partid (B) = reference Interne de l'article (fallback module+fig).
    if item.get("ref_interne"):
        row["partid"] = item["ref_interne"]
    elif meta.get("module") and item.get("fig"):
        row["partid"] = f"{meta['module']}-{item['fig']}"

    # Constantes document repetees sur chaque ligne.
    if meta.get("module"):
        row["module"] = meta["module"]
    if meta.get("otan_supplier"):
        row["otan_supplier"] = meta["otan_supplier"]

    return row


def module_header_rows(header_meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Construit le bloc en-tete module (0, 1 ou 2 lignes) depuis header_meta.

    Renvoie une liste vide si aucune metadonnee module n'est fournie (V1 :
    on ecrit alors directement les articles sans bloc en-tete)."""
    module = (header_meta or {}).get("module")
    if not module:
        return []

    title = header_meta.get("bom_title") or ""
    supplier = header_meta.get("otan_supplier") or ""
    drw = header_meta.get("drw") or ""
    top = header_meta.get("top_assembly") or ""

    # Ligne 1 du bloc : identifie le module + illustration.
    r1 = blank_row()
    r1["module"] = module
    r1["partid"] = f"MOD{module}"
    r1["description"] = title
    r1["otan_supplier"] = supplier
    if drw:
        r1["drw"] = drw

    rows = [r1]

    # Ligne 2 du bloc : top-assembly (ex. +1A) si fourni.
    if top:
        r2 = blank_row()
        r2["module"] = module
        r2["partid"] = f"{module}{top}"
        r2["fig"] = top
        r2["description"] = title
        r2["otan_supplier"] = supplier
        r2["qty_assy"] = "REF"
        rows.append(r2)

    return rows
