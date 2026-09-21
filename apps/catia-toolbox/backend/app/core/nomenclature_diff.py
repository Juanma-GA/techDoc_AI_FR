"""Etape 1 (bis) - Comparaison de deux nomenclatures (versions V0 vs V1).

Fonction pure : compare deux BOM a plat (V0 = base, V1 = nouvelle) appariees
par **SIN** (le « signe ») et renvoie :
  - les SIN **ajoutes** (presents en V1, absents en V0) ;
  - les SIN **supprimes** (presents en V0, absents en V1) ;
  - les SIN **modifies** pour un meme signe : le PN change entre V0 et V1.

Detection du changement de PN : on compare les colonnes **OLD P/N entre elles**
et **NEW P/N entre elles** d'une version a l'autre. Un SIN est « modifie » des
que l'OLD *ou* le NEW change. Quand la nomenclature n'a pas de colonne P/N
dediee, le **CATPart** de la ligne fait office de P/N (fallback).

Les informations **OLD PN** de V0 et **NEW PN** de V1 sont reportees pour
rendre le remplacement directement exploitable.

Deterministe, sans DB : opere sur des dicts {sin, catpart, old_pn, new_pn, ...}.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from itertools import pairwise
from typing import Literal


def _old_pn_of(item: dict) -> str:
    """OLD P/N effectif : colonne OLD P/N, sinon le CATPart de la version."""
    return str(item.get("old_pn") or item.get("catpart") or "").strip()


def _new_pn_of(item: dict) -> str:
    """NEW P/N effectif : colonne NEW P/N, sinon le CATPart de la version."""
    return str(item.get("new_pn") or item.get("catpart") or "").strip()


def _designation_of(item: dict) -> str:
    return str(item.get("designation") or "").strip()


def _by_sin(items: Iterable[dict]) -> dict[str, dict]:
    """Index par SIN (derniere ligne gagnante si doublon). Ignore les SIN vides."""
    out: dict[str, dict] = {}
    for it in items:
        sin = str(it.get("sin") or "").strip()
        if sin:
            out[sin] = it
    return out


def compare_runs(items_a: Iterable[dict], items_b: Iterable[dict]) -> dict:
    """Compare deux nomenclatures (A = V0 base, B = V1 nouvelle) par SIN.

    Retour : {added_sin[], removed_sin[], changed_pn[]}. Chaque changement porte
    le SIN, l'OLD PN de la base, le NEW PN de la nouvelle version et la
    designation (pas de revisions).
    """
    a = _by_sin(items_a)
    b = _by_sin(items_b)

    added_sin = [
        {
            "sin": sin,
            "old_pn": "",
            "new_pn": _new_pn_of(b[sin]),
            "designation": _designation_of(b[sin]),
        }
        for sin in b
        if sin not in a
    ]
    removed_sin = [
        {
            "sin": sin,
            "old_pn": _old_pn_of(a[sin]),
            "new_pn": "",
            "designation": _designation_of(a[sin]),
        }
        for sin in a
        if sin not in b
    ]
    changed_pn = []
    for sin in a:
        if sin not in b:
            continue
        # Changement de PN = OLD(V0) != OLD(V1) *ou* NEW(V0) != NEW(V1) (colonnes
        # OLD comparees entre elles, NEW entre elles).
        old_changed = _old_pn_of(a[sin]) != _old_pn_of(b[sin])
        new_changed = _new_pn_of(a[sin]) != _new_pn_of(b[sin])
        if old_changed or new_changed:
            changed_pn.append(
                {
                    "sin": sin,
                    "old_pn": _old_pn_of(a[sin]),
                    "new_pn": _new_pn_of(b[sin]),
                    "designation": _designation_of(b[sin]) or _designation_of(a[sin]),
                }
            )

    added_sin.sort(key=lambda e: e["sin"])
    removed_sin.sort(key=lambda e: e["sin"])
    changed_pn.sort(key=lambda e: e["sin"])
    return {"added_sin": added_sin, "removed_sin": removed_sin, "changed_pn": changed_pn}


def summarize(diff: dict) -> dict[str, int]:
    return {
        "added": len(diff["added_sin"]),
        "removed": len(diff["removed_sin"]),
        "changed": len(diff["changed_pn"]),
        "total": len(diff["added_sin"]) + len(diff["removed_sin"]) + len(diff["changed_pn"]),
    }


def comparison_pairs(
    run_ids: list[uuid.UUID],
    *,
    mode: Literal["chronology", "reference"],
    reference_run_id: uuid.UUID | None = None,
) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Construit les paires sans modifier le moteur historique a deux versions."""
    if len(run_ids) < 2:
        raise ValueError("Deux nomenclatures au minimum sont requises.")
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("Chaque nomenclature ne peut etre selectionnee qu'une fois.")
    if mode == "chronology":
        return list(pairwise(run_ids))
    reference = reference_run_id or run_ids[0]
    if reference not in run_ids:
        raise ValueError("La nomenclature de reference doit faire partie de la selection.")
    return [(reference, run_id) for run_id in run_ids if run_id != reference]


def build_matrix(
    run_ids: list[uuid.UUID],
    items_by_run: dict[uuid.UUID, list[dict]],
    comparisons: list[dict],
    *,
    mode: Literal["chronology", "reference"],
    reference_run_id: uuid.UUID | None = None,
) -> list[dict]:
    """Construit une ligne par SIN et une cellule par version selectionnee."""
    indexed = {run_id: _by_sin(items_by_run[run_id]) for run_id in run_ids}
    all_sins = sorted({sin for items in indexed.values() for sin in items})
    state_by_cell: dict[tuple[uuid.UUID, str], str] = {}

    if mode == "reference":
        reference = reference_run_id or run_ids[0]
        for sin in all_sins:
            state_by_cell[(reference, sin)] = "reference"

    for comparison in comparisons:
        other_id = comparison["other_run_id"]
        diff = comparison["diff"]
        for entry in diff["added_sin"]:
            state_by_cell[(other_id, entry["sin"])] = "added"
        for entry in diff["removed_sin"]:
            state_by_cell[(other_id, entry["sin"])] = "removed"
        for entry in diff["changed_pn"]:
            state_by_cell[(other_id, entry["sin"])] = "changed"

    rows: list[dict] = []
    for sin in all_sins:
        designation = next(
            (
                _designation_of(indexed[run_id][sin])
                for run_id in reversed(run_ids)
                if sin in indexed[run_id] and _designation_of(indexed[run_id][sin])
            ),
            "",
        )
        cells = []
        for run_id in run_ids:
            item = indexed[run_id].get(sin)
            cells.append(
                {
                    "run_id": run_id,
                    "present": item is not None,
                    "pn": _new_pn_of(item) if item else "",
                    "state": state_by_cell.get((run_id, sin), "unchanged"),
                }
            )
        rows.append({"sin": sin, "designation": designation, "cells": cells})
    return rows
