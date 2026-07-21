"""Etape 1 (bis) - Comparaison de deux nomenclatures (versions V0 vs V1).

Fonction pure : compare deux BOM a plat (V0 = base, V1 = nouvelle) appariees
par **SIN** (le « signe ») et renvoie :
  - les SIN **ajoutes** (presents en V1, absents en V0) ;
  - les SIN **supprimes** (presents en V0, absents en V1) ;
  - les SIN **modifies** pour un meme signe : le PN change entre V0 et V1.

Seule l'information **OLD PN** (le PN de la piece dans V0, a rechercher /
remplacer) est produite par la comparaison. Les colonnes NEW PN / OLD REV /
NEW REV de la nomenclature ne servent PAS ici (elles sont conservees dans
l'analyse de nomenclature pour l'etape de remplacement Composer).

Deterministe, sans DB : opere sur des dicts {sin, catpart, ...}. Le PN d'une
ligne est le **CATPart** de sa version (numero de piece present dans la BOM).
"""

from __future__ import annotations

from typing import Iterable


def _pn_of(item: dict) -> str:
    """PN effectif d'une ligne = CATPart de la version (fallback new/old PN)."""
    return str(
        item.get("catpart") or item.get("new_pn") or item.get("old_pn") or ""
    ).strip()


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
        # OLD PN = PN de V0 ; le changement se detecte en comparant au PN de V1,
        # mais seul l'OLD PN est reporte (a rechercher / remplacer).
        old_pn = _pn_of(a[sin])
        if old_pn != _pn_of(b[sin]):
            changed_pn.append(
                {"sin": sin, "old_pn": old_pn, "designation": _designation_of(a[sin])}
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
