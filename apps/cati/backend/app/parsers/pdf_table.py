"""Extraction de la nomenclature (BOM) d'un PDF plan de montage CATI.

Un article CATI occupe 3 sous-lignes (Client / Interne / Fournisseur) ; FIG REP,
DESIGNATION et QUANTITE(ES) ne sont renseignes que sur la 1re. Le coeur du
parseur est le REGROUPEMENT de ces sous-lignes en un enregistrement article.

Cascade :
  1. `page.find_tables()` (chemin nominal : la grille est propre) + detection
     d'en-tete (`column_map`) + regroupement par role de la colonne "Code".
  2. Repli texte lineaire (`get_text`) si find_tables ne donne rien : machine a
     etats sur le motif observe (FIG REP / designation / qty, puis triplets
     "<role> <reference>").
  3. Filet LLM optionnel (`chat_json`) si 1 et 2 echouent ET `llm_enabled`.

Champs logiques produits par article :
  fig, figreflink, aplomb, description, matiere, ref_client, ref_interne,
  ref_fournisseur, qty, symbole, source_page.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import fitz  # PyMuPDF

from app.core.column_map import detect_header, norm, role_of

# FIG REP : 1 a 4 chiffres, suffixe lettre optionnel (10A, 120A, 5, ...).
_FIG_RE = re.compile(r"^\d{1,4}[A-Za-z]?$")
# Reference d'un role : alphanumerique (C1023, I1023, F1023, ...).
_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/\-]*$")

_REF_FIELDS = ("ref_client", "ref_interne", "ref_fournisseur")


def _split_aplomb(designation: str) -> tuple[str, str]:
    """'.Bati equipe' -> ('.', 'Bati equipe'). Compte les points d'indentation."""
    d = (designation or "").strip()
    i = 0
    while i < len(d) and d[i] == ".":
        i += 1
    aplomb = "." * i if i else ""
    return aplomb, d[i:].strip()


def _figreflink(fig: str) -> Optional[int]:
    """Partie numerique du FIG REP ('10A' -> 10)."""
    m = re.match(r"^(\d+)", fig or "")
    return int(m.group(1)) if m else None


def _new_item(fig: str, designation: str, qty: object, symbole: object, page: int) -> dict[str, Any]:
    aplomb, desc = _split_aplomb(str(designation or ""))
    return {
        "fig": fig,
        "figreflink": _figreflink(fig),
        "aplomb": aplomb,
        "description": desc,
        "matiere": "",
        "ref_client": "",
        "ref_interne": "",
        "ref_fournisseur": "",
        "qty": ("" if qty is None else str(qty).strip()),
        "symbole": ("" if symbole is None else str(symbole).strip()),
        "source_page": page,
    }


def _finalize(item: dict[str, Any]) -> bool:
    """Un article est valide s'il a un fig + (une designation OU une reference)."""
    has_ref = any(item.get(f) for f in _REF_FIELDS)
    return bool(item.get("fig")) and bool(item.get("description") or has_ref)


# ---------------------------------------------------------------------------
# 1. Chemin nominal : table structuree (find_tables)
# ---------------------------------------------------------------------------
def _cell(row: list, idx: Optional[int]) -> object:
    if idx is None or idx < 0 or idx >= len(row):
        return None
    return row[idx]


def group_grid(grid: list[list], page: int = 1) -> list[dict]:
    """Regroupe une grille de table (list[list]) en articles CATI.

    Fonction PURE (testable sans PDF) : detecte l'en-tete, puis regroupe les
    sous-lignes Client/Interne/Fournisseur par FIG REP. Renvoie [] si la grille
    n'est pas une nomenclature exploitable (pas de colonnes fig+code).
    """
    if not grid:
        return []
    header_idx, colmap = detect_header(grid)
    if header_idx < 0 or "code" not in colmap or "fig" not in colmap:
        return []

    c_fig = colmap["fig"]
    c_desig = colmap.get("designation")
    c_code = colmap["code"]
    c_ref = colmap.get("reference")
    c_qty = colmap.get("qty")
    c_sym = colmap.get("symbole")

    items: list[dict] = []
    current: Optional[dict] = None
    for row in grid[header_idx + 1:]:
        role = role_of(_cell(row, c_code))
        fig_val = _cell(row, c_fig)
        fig = str(fig_val).strip() if fig_val else ""

        # On ne traite que les lignes "de donnees". Un debut d'article porte
        # TOUJOURS un role (Client) sur sa 1re sous-ligne : exiger `role` ecarte
        # le titre, le sous-en-tete ET la ligne des numeros de colonne (ex.
        # "1 2 7 3A ...", qui a un fig mais aucun role).
        if fig and _FIG_RE.match(fig) and role:
            if current and _finalize(current):
                items.append(current)
            current = _new_item(
                fig,
                _cell(row, c_desig) if c_desig is not None else "",
                _cell(row, c_qty) if c_qty is not None else None,
                _cell(row, c_sym) if c_sym is not None else None,
                page,
            )
            if c_ref is not None:
                current[role] = str(_cell(row, c_ref) or "").strip()
        elif current is not None and role and c_ref is not None:
            current[role] = str(_cell(row, c_ref) or "").strip()
            # designation qui deborde sur une sous-ligne
            desc_more = _cell(row, c_desig) if c_desig is not None else None
            if desc_more and str(desc_more).strip():
                current["description"] = f"{current['description']} {str(desc_more).strip()}".strip()

    if current and _finalize(current):
        items.append(current)
    return items


def _extract_via_tables(doc: "fitz.Document") -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    items: list[dict] = []

    for pno in range(doc.page_count):
        page = doc[pno]
        try:
            found = page.find_tables()
        except Exception as e:  # noqa: BLE001
            warnings.append(f"find_tables page {pno + 1}: {type(e).__name__}")
            continue
        for table in found.tables:
            items.extend(group_grid(table.extract(), pno + 1))

    return items, warnings


# ---------------------------------------------------------------------------
# 2. Repli texte lineaire
# ---------------------------------------------------------------------------
def _extract_via_text(doc: "fitz.Document") -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    items: list[dict] = []

    role_labels = {"client": "ref_client", "interne": "ref_interne", "fournisseur": "ref_fournisseur"}

    for pno in range(doc.page_count):
        lines = [ln.strip() for ln in doc[pno].get_text("text").splitlines() if ln.strip()]
        # Cherche le debut du corps (apres l'en-tete) : 1re ligne FIG REP.
        current: Optional[dict] = None
        pending_desc: Optional[str] = None
        for ln in lines:
            first = ln.split()[0] if ln.split() else ""
            low = norm(ln)
            role = next((f for k, f in role_labels.items() if low.startswith(k)), None)

            if role:
                if current is not None:
                    parts = ln.split(None, 1)
                    ref = parts[1].strip() if len(parts) > 1 else ""
                    if ref and _REF_RE.match(ref.split()[0]):
                        current[role] = ref.split()[0]
                continue

            if _FIG_RE.match(first) and (first[-1].isalpha() or len(lines) < 3):
                # Debut d'un nouvel article.
                if current and _finalize(current):
                    items.append(current)
                current = _new_item(first, "", None, None, pno + 1)
                pending_desc = None
                rest = ln[len(first):].strip()
                if rest:
                    aplomb, desc = _split_aplomb(rest)
                    current["aplomb"], current["description"] = aplomb, desc
                continue

            if current is not None:
                # Ligne de designation ou de quantite qui suit le FIG REP.
                if ln.startswith(".") and not current["description"]:
                    aplomb, desc = _split_aplomb(ln)
                    current["aplomb"], current["description"] = aplomb, desc
                elif not current["qty"] and re.match(r"^[\d.,]+(\s*\w+)?$", ln):
                    current["qty"] = ln.strip()
                elif not current["description"]:
                    pending_desc = ln

        if current and _finalize(current):
            items.append(current)

    if not items:
        warnings.append("repli texte : aucun article detecte")
    return items, warnings


# ---------------------------------------------------------------------------
# 3. Filet LLM (optionnel)
# ---------------------------------------------------------------------------
_LLM_SYSTEM = (
    "Tu extrais une nomenclature (BOM) depuis le texte d'un plan de montage. "
    "Renvoie STRICTEMENT un objet JSON {\"items\": [...]} ou chaque item a les "
    "cles: fig, description, qty, ref_client, ref_interne, ref_fournisseur. "
    "N'invente rien ; laisse une chaine vide si absent."
)


def _extract_via_llm(doc: "fitz.Document", mistral: Any) -> tuple[list[dict], list[str]]:
    text = "\n".join(doc[p].get_text("text") for p in range(doc.page_count))
    try:
        parsed = mistral.chat_json(
            messages=[
                {"role": "system", "content": _LLM_SYSTEM},
                {"role": "user", "content": text[:20000]},
            ],
        )
    except Exception as e:  # noqa: BLE001 - fallback gracieux, jamais 5xx
        return [], [f"filet LLM indisponible : {type(e).__name__}"]

    raw = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(raw, list):
        return [], ["filet LLM : reponse sans liste 'items'"]

    items: list[dict] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        fig = str(entry.get("fig") or "").strip()
        item = _new_item(fig, str(entry.get("description") or ""), entry.get("qty"), None, 0)
        for f in _REF_FIELDS:
            item[f] = str(entry.get(f) or "").strip()
        if _finalize(item):
            items.append(item)
    return items, []


# ---------------------------------------------------------------------------
# Entree publique
# ---------------------------------------------------------------------------
def extract_bom(
    path: str,
    *,
    mistral: Any = None,
    llm_enabled: bool = False,
) -> dict[str, Any]:
    """Extrait la nomenclature d'un PDF -> {items, warnings, method, page_count}.

    `method` : 'deterministic' | 'llm' | 'mixed'. Le filet LLM n'est sollicite
    que si l'extraction deterministe ne rend aucun article ET `llm_enabled`.
    """
    doc = fitz.open(path)
    try:
        page_count = doc.page_count
        items, warnings = _extract_via_tables(doc)
        method = "deterministic"

        if not items:
            t_items, t_warn = _extract_via_text(doc)
            warnings += t_warn
            if t_items:
                items = t_items

        if not items and llm_enabled and mistral is not None:
            l_items, l_warn = _extract_via_llm(doc, mistral)
            warnings += l_warn
            if l_items:
                items = l_items
                method = "llm"
    finally:
        doc.close()

    for idx, it in enumerate(items):
        it["order_index"] = idx

    return {
        "items": items,
        "warnings": warnings,
        "method": method,
        "page_count": page_count,
    }


def dumps_meta(warnings: list[str], detected: Optional[dict] = None) -> str:
    """Serialise les metadonnees d'extraction pour la colonne `extraction_meta`."""
    return json.dumps({"warnings": warnings, "detected": detected or {}}, ensure_ascii=False)
