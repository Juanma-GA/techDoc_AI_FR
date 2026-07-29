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

Seule l'information **OLD PN** (le PN de la piece dans V0, a rechercher /
remplacer) est reportee par la comparaison.

Deterministe, sans DB : opere sur des dicts {sin, catpart, old_pn, new_pn, ...}.
"""

from __future__ import annotations

from typing import Iterable


def _pn_of(item: dict) -> str:
    """PN effectif d'une ligne = CATPart de la version (fallback new/old PN)."""
    return str(
        item.get("catpart") or item.get("new_pn") or item.get("old_pn") or ""
    ).strip()


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

    Retour : {added_sin[], removed_sin[], changed_pn[]}. Chaque entree ne porte
    que le SIN, l'OLD PN et la designation (pas de NEW PN / revisions).
    """
    a = _by_sin(items_a)
    b = _by_sin(items_b)

    added_sin = [
        {"sin": sin, "pn": _pn_of(b[sin]), "designation": _designation_of(b[sin])}
        for sin in b
        if sin not in a
    ]
    removed_sin = [
        {"sin": sin, "pn": _pn_of(a[sin]), "designation": _designation_of(a[sin])}
        for sin in a
        if sin not in b
    ]
    changed_pn = []
    for sin in a:
        if sin not in b:
            continue
        # Changement de PN = OLD(V0) != OLD(V1) *ou* NEW(V0) != NEW(V1) (colonnes
        # OLD comparees entre elles, NEW entre elles). Seul l'OLD PN de V0 est
        # reporte (a rechercher / remplacer).
        old_changed = _old_pn_of(a[sin]) != _old_pn_of(b[sin])
        new_changed = _new_pn_of(a[sin]) != _new_pn_of(b[sin])
        if old_changed or new_changed:
            changed_pn.append(
                {"sin": sin, "old_pn": _old_pn_of(a[sin]), "designation": _designation_of(a[sin])}
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
