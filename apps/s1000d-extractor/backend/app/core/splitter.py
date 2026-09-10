"""Decoupage d'un document en plusieurs Data Modules (etape 2 du wizard).

Une publication reelle = plusieurs DM (chaque section est un DM distinct, avec
son propre type : descriptif / procedure / IPD). Cet outil scinde l'arbre IR au
niveau choisi par l'utilisateur :

    chapter (1)  -> 1 DM par chapitre  ("0", "1", "2"...)
    section (2)  -> 1 DM par section   ("0.1", "0.2", "1.2"...)
    subsection(3)-> 1 DM par sous-section ("0.2.1", "1.2.6"...)

Chaque DM est un sous-arbre autonome (titre + contenu) que le pipeline type,
resout et serialise independamment.

Quand une DMRL est fournie, elle PRIME : le decoupage suit la liste des DM
attendus par le client (`split_by_dmrl`) au lieu du niveau de titre.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core import dmrl
from app.core.dmrl import DmrlEntry
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
    # Contenu du document non couvert par la DMRL : le libelle est rendu cote UI
    # (pas de chaine d'affichage en dur dans le moteur).
    is_orphan: bool = False
    dmrl_index: int | None = None


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


# --- decoupage pilote par la DMRL -------------------------------------------

def ir_to_text(root: IRNode) -> str:
    """Texte lineaire de l'arbre (ordre de lecture) - support de l'appariement
    des titres de la DMRL sur le contenu du document."""
    return "\n".join(n.text for n in root.walk() if n.text)


def _flat_nodes(root: IRNode) -> list[IRNode]:
    """Aplatit l'arbre en ordre de lecture, sans duplication de contenu.

    Une section devient un noeud TITRE seul (ses enfants sont remontes au meme
    niveau) ; les autres noeuds sont repris tels quels avec leurs enfants (un
    `item-sequence` garde ses `item`).
    """
    out: list[IRNode] = []

    def walk(node: IRNode) -> None:
        for child in node.children:
            if child.kind == "section":
                out.append(IRNode(
                    id=child.id, kind="section", text=child.text, level=child.level,
                    form=child.form, page=child.page, zone=child.zone,
                    context=child.context, confidence=child.confidence,
                ))
                walk(child)
            else:
                out.append(child)

    walk(root)
    return out


def match_dmrl(root: IRNode, dmrl_data: list[DmrlEntry]) -> list[tuple[int | None, str]]:
    """Pour chaque entree DMRL : index du noeud-titre apparie + rang d'appariement.

    Sert AVANT le decoupage : l'utilisateur valide la DMRL en voyant ce qui a
    ete retrouve dans son document, et A QUEL POINT c'est sur.
    """
    nodes = _flat_nodes(root)
    norm_nodes = [dmrl.normalize(n.text) for n in nodes]
    out: list[tuple[int | None, str]] = []
    cursor = 0
    for entry in dmrl_data:
        idx, rank = dmrl.find_title(norm_nodes, dmrl.normalize(entry.title), cursor)
        out.append((idx, rank))
        if idx is not None:
            cursor = idx + 1
    return out


def match_report(root: IRNode, dmrl_data: list[DmrlEntry]) -> list[dict]:
    """Rapport d'appariement DMRL <-> document : une ligne par entree."""
    nodes = _flat_nodes(root)
    matches = match_dmrl(root, dmrl_data)
    return [
        {
            **entry.to_dict(),
            "index": i,
            "matched": idx is not None,
            "match_rank": rank,
            "page": nodes[idx].page if idx is not None else None,
            "matched_text": nodes[idx].text if idx is not None else "",
        }
        for i, (entry, (idx, rank)) in enumerate(zip(dmrl_data, matches, strict=True))
    ]


def split_by_dmrl(root: IRNode, dmrl_data: list[DmrlEntry]) -> list[DmUnit]:
    """Decoupe l'IR selon les DM attendus par la DMRL.

    Le titre de chaque entree DMRL est apparie sur les noeuds du document ; le
    contenu d'un DM = les noeuds situes entre son titre et le titre suivant.

    Rien n'est jete : le contenu qui precede le premier DM (pages de garde,
    preface, avertissements) devient un DM marque `is_orphan`, et les entrees
    non retrouvees produisent un DM VIDE — l'humain voit ce qui reste a traiter.
    """
    nodes = _flat_nodes(root)
    matches = match_dmrl(root, dmrl_data)

    anchors: list[tuple[int, int, DmrlEntry]] = []
    missing: list[tuple[int, DmrlEntry]] = []
    for dmrl_index, (entry, (idx, _rank)) in enumerate(zip(dmrl_data, matches, strict=True)):
        if idx is None:
            missing.append((dmrl_index, entry))
        else:
            anchors.append((idx, dmrl_index, entry))
    anchors.sort(key=lambda t: t[0])

    dms: list[DmUnit] = []
    if anchors and anchors[0][0] > 0:
        syn = IRNode(id="dm1-root", kind="section", level=0, children=list(nodes[:anchors[0][0]]))
        dms.append(DmUnit(
            dm_id="dm1", title="", root=syn, page=nodes[0].page,
            node_count=len(syn.walk()), is_orphan=True,
        ))

    for i, (idx, dmrl_index, entry) in enumerate(anchors):
        end = anchors[i + 1][0] if i + 1 < len(anchors) else len(nodes)
        dm_id = f"dm{len(dms) + 1}"
        syn = IRNode(id=f"{dm_id}-root", kind="section", level=0,
                     children=list(nodes[idx + 1:end]))
        dms.append(DmUnit(
            dm_id=dm_id, title=entry.title or f"Data Module {i + 1}",
            root=syn, page=nodes[idx].page, node_count=len(syn.walk()),
            dmrl_index=dmrl_index,
        ))
    for dmrl_index, entry in missing:
        dm_id = f"dm{len(dms) + 1}"
        dms.append(DmUnit(
            dm_id=dm_id, title=entry.title, root=IRNode(id=f"{dm_id}-root", kind="section", level=0),
            node_count=1, dmrl_index=dmrl_index,
        ))
    return dms
