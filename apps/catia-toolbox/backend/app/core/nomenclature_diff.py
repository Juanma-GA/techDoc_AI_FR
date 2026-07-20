"""Etape 1 (bis) - Comparaison de deux nomenclatures (versions V0 vs V1).

Fonction pure : compare deux BOM a plat (V0 = base, V1 = nouvelle) appariees
par **SIN** (le « signe ») et renvoie :
  - les SIN **ajoutes** (presents en V1, absents en V0) ;
  - les SIN **supprimes** (presents en V0, absents en V1) ;
  - les SIN **evolues** pour un meme signe, distingues par la nature du
    changement :
      * `pn_evolue`  : le PN change entre V0 et V1 (piece remplacee) -> on
        renseigne le nouveau PN ET la nouvelle revision ;
      * `rev_evolue` : le PN reste identique mais la revision change (meme
        piece, indice mis a jour) -> on conserve le meme PN et on met a jour
        la revision.

Deterministe, sans DB : opere sur des dicts {sin, catpart, version, ...}. Le PN
d'une ligne est le **CATPart** de sa version (numero de piece reellement present
dans la BOM), la revision est la **version** (indice).
"""

from __future__ import annotations

from typing import Iterable


def _pn_of(item: dict) -> str:
    """PN effectif d'une ligne = CATPart de la version (fallback new/old PN)."""
    return str(
        item.get("catpart") or item.get("new_pn") or item.get("old_pn") or ""
    ).strip()


def _rev_of(item: dict) -> str:
    """Revision effective d'une ligne = indice de la version (fallback new_rev)."""
    return str(item.get("version") or item.get("new_rev") or "").strip()


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

    Retour : {added_sin[], removed_sin[], changed_pn[]}. Chaque entree
    `changed_pn` porte un champ `kind` (`pn_evolue` | `rev_evolue`).
    """
    a = _by_sin(items_a)
    b = _by_sin(items_b)

    added_sin = [
        {
            "sin": sin,
            "pn": _pn_of(b[sin]),
            "rev": _rev_of(b[sin]),
            "designation": _designation_of(b[sin]),
        }
        for sin in b
        if sin not in a
    ]
    removed_sin = [
        {
            "sin": sin,
            "pn": _pn_of(a[sin]),
            "rev": _rev_of(a[sin]),
            "designation": _designation_of(a[sin]),
        }
        for sin in a
        if sin not in b
    ]
    changed_pn = []
    for sin in a:
        if sin not in b:
            continue
        old_pn, new_pn = _pn_of(a[sin]), _pn_of(b[sin])
        old_rev, new_rev = _rev_of(a[sin]), _rev_of(b[sin])
        if old_pn != new_pn:
            kind = "pn_evolue"  # piece remplacee : nouveau PN + nouvelle revision
        elif old_rev != new_rev:
            kind = "rev_evolue"  # meme PN, revision mise a jour
        else:
            continue  # inchange
        changed_pn.append(
            {
                "sin": sin,
                "kind": kind,
                "old_pn": old_pn,
                "new_pn": new_pn,
                "old_rev": old_rev,
                "new_rev": new_rev,
                "designation": _designation_of(b[sin]),
            }
        )

    added_sin.sort(key=lambda e: e["sin"])
    removed_sin.sort(key=lambda e: e["sin"])
    changed_pn.sort(key=lambda e: e["sin"])
    return {"added_sin": added_sin, "removed_sin": removed_sin, "changed_pn": changed_pn}


def summarize(diff: dict) -> dict[str, int]:
    pn_evolue = sum(1 for e in diff["changed_pn"] if e["kind"] == "pn_evolue")
    rev_evolue = sum(1 for e in diff["changed_pn"] if e["kind"] == "rev_evolue")
    return {
        "added": len(diff["added_sin"]),
        "removed": len(diff["removed_sin"]),
        "changed": len(diff["changed_pn"]),
        "pn_evolue": pn_evolue,
        "rev_evolue": rev_evolue,
        "total": len(diff["added_sin"]) + len(diff["removed_sin"]) + len(diff["changed_pn"]),
    }
