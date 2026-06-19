"""Decoupage d'un document en plusieurs Data Modules (etape 2 du wizard).

Une publication reelle = plusieurs DM (chaque section est un DM distinct, avec
son propre type : descriptif / procedure / IPD). Cet outil scinde l'arbre IR au
niveau choisi par l'utilisateur :

    chapter (1)  -> 1 DM par chapitre  ("0", "1", "2"...)
    section (2)  -> 1 DM par section   ("0.1", "0.2", "1.2"...)
    subsection(3)-> 1 DM par sous-section ("0.2.1", "1.2.6"...)

Chaque DM est un sous-arbre autonome (titre + contenu) que le pipeline type,
resout et serialise independamment.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.ir import IRNode

_LEVEL = {"chapter": 1, "section": 2, "subsection": 3}


def level_of(split_level: str) -> int:
    return _LEVEL.get(split_level, 2)


@dataclass
class DmUnit:
    dm_id: str
    title: str
    root: IRNode                       # racine synthetique : children = contenu du DM
    page: int | None = None
    node_count: int = 0


def _collect(node: IRNode, depth: int, out: list[IRNode]) -> None:
    """Collecte les sections-racines de DM : la 1ere section rencontree dont le
    niveau >= depth (on descend tant que les sections sont au-dessus du niveau)."""
    for child in node.children:
        if child.kind != "section":
            continue
        if child.level is not None and child.level >= depth:
            out.append(child)
        else:
            _collect(child, depth, out)


def split_into_dms(root: IRNode, split_level: str) -> list[DmUnit]:
    depth = level_of(split_level)
    sections: list[IRNode] = []
    _collect(root, depth, sections)

    # Aucune section au niveau voulu -> tout le document devient un seul DM.
    if not sections:
        title = next((c.text for c in root.children if c.kind == "section" and c.text), "Document")
        syn = IRNode(id="dm1-root", kind="section", level=0, children=list(root.children))
        return [DmUnit(dm_id="dm1", title=title, root=syn, node_count=len(syn.walk()))]

    dms: list[DmUnit] = []
    for i, sec in enumerate(sections, start=1):
        dm_id = f"dm{i}"
        syn = IRNode(id=f"{dm_id}-root", kind="section", level=0, children=list(sec.children))
        dms.append(DmUnit(
            dm_id=dm_id,
            title=sec.text or f"Data Module {i}",
            root=syn,
            page=sec.page,
            node_count=len(syn.walk()),
        ))
    return dms
