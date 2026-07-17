"""Etape 1 (bis) - Comparaison de deux nomenclatures (versions A vs B).

Fonction pure : compare deux listes de lignes de nomenclature par **SIN**
(le « signe ») et renvoie :
  - les SIN **ajoutes** (presents en B, absents en A) ;
  - les SIN **supprimes** (presents en A, absents en B) ;
  - les PN **evolues** pour un meme SIN (PN et/ou indice differents entre A et B).

Deterministe, sans DB : opere sur des dicts {sin, pn, rev, ...}. Le PN retenu
est le CATPart (ou le nouveau PN si renseigne), l'indice est la version.
"""

from __future__ import annotations

from typing import Iterable


def _pn_of(item: dict) -> str:
    """PN effectif d'une ligne : nouveau PN si renseigne, sinon CATPart."""
    return str(item.get("new_pn") or item.get("catpart") or "").strip()


def _rev_of(item: dict) -> str:
    return str(item.get("new_rev") or item.get("version") or "").strip()


def _by_sin(items: Iterable[dict]) -> dict[str, dict]:
    """Index par SIN (derniere ligne gagnante si doublon). Ignore les SIN vides."""
    out: dict[str, dict] = {}
    for it in items:
        sin = str(it.get("sin") or "").strip()
        if sin:
            out[sin] = it
    return out


def compare_runs(items_a: Iterable[dict], items_b: Iterable[dict]) -> dict:
    """Compare deux nomenclatures (A = base, B = nouvelle) par SIN.

    Retour : {added_sin[], removed_sin[], changed_pn[]} ou chaque entree porte
    le SIN et le PN/indice concerne.
    """
    a = _by_sin(items_a)
    b = _by_sin(items_b)

    added_sin = [
        {"sin": sin, "pn": _pn_of(b[sin]), "designation": str(b[sin].get("designation") or "").strip()}
        for sin in b
        if sin not in a
    ]
    removed_sin = [
        {"sin": sin, "pn": _pn_of(a[sin]), "designation": str(a[sin].get("designation") or "").strip()}
        for sin in a
        if sin not in b
    ]
    changed_pn = []
    for sin in a:
        if sin not in b:
            continue
        old_pn, new_pn = _pn_of(a[sin]), _pn_of(b[sin])
        old_rev, new_rev = _rev_of(a[sin]), _rev_of(b[sin])
        if old_pn != new_pn or old_rev != new_rev:
            changed_pn.append(
                {
                    "sin": sin,
                    "old_pn": old_pn,
                    "new_pn": new_pn,
                    "old_rev": old_rev,
                    "new_rev": new_rev,
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
