"""Resolveur : IR (contexte + forme) -> candidats d'elements S1000D.

C'est le moteur generique, ecrit UNE fois, jamais reecrit par document. Le
choix de la balise vient du *content-model S1000D* selon le CONTEXTE
(descriptif vs procedural) - PAS du BREX. (Correction metier : le BREX est une
porte de validation en aval, il ne genere pas les elements ; il les contraint.)

Le coeur est une matrice (contexte x kind x forme) -> liste de candidats. Quand
plusieurs balises sont legitimes (ex. une liste a puces : `para`/`randomList`
en descriptif, `proceduralStep` en procedural), on emet PLUSIEURS candidats
ordonnes par score : le 1er est emis par defaut, les autres sont conserves pour
la revue humaine (toggle 1-clic) et tracus en commentaire `<!-- alt: ... -->`.
"""

from __future__ import annotations

from app.core.ir import Candidate, Context, IRNode

# Vocabulaire d'admonition stable entre Issues 4.2 et 5.0.
_ADMONITION_ELEMENT = {
    "warning": "warning",
    "caution": "caution",
    "note": "note",
}


def _list_candidates(node: IRNode, context: Context) -> list[Candidate]:
    ordered = node.form == "ordered"
    desc_list = "sequentialList" if ordered else "randomList"
    if context == "procedural":
        return [
            Candidate("proceduralStep", 0.8, "Liste d'actions en contexte procedural"),
            Candidate(desc_list, 0.4, "Alternative : liste descriptive si non-procedurale"),
        ]
    if context == "descriptive":
        return [Candidate(desc_list, 0.85, "Liste en contexte descriptif")]
    # Contexte indetermine : on expose les deux solutions, l'humain tranche.
    return [
        Candidate(desc_list, 0.5, "Contexte indetermine - hypothese descriptive"),
        Candidate("proceduralStep", 0.5, "Contexte indetermine - hypothese procedurale"),
    ]


def _paragraph_candidates(context: Context) -> list[Candidate]:
    if context == "procedural":
        return [
            Candidate("proceduralStep", 0.6, "Paragraphe en procedure - probable etape"),
            Candidate("para", 0.4, "Alternative : para descriptif dans la procedure"),
        ]
    return [Candidate("para", 0.9, "Paragraphe courant")]


def _section_candidates(context: Context) -> list[Candidate]:
    if context == "procedural":
        return [Candidate("proceduralStep", 0.7, "Section d'une procedure -> etape englobante")]
    return [Candidate("levelledPara", 0.9, "Section descriptive -> levelledPara")]


def candidates_for(node: IRNode) -> list[Candidate]:
    """Candidats S1000D pour un noeud, selon son contexte et sa forme."""
    ctx = node.context
    if node.kind == "admonition" and node.admonition:
        return [Candidate(_ADMONITION_ELEMENT[node.admonition], 0.95, "Admonition detectee")]
    if node.kind == "figure":
        return [Candidate("figure", 0.85, "Legende de figure detectee")]
    if node.kind == "table":
        return [Candidate("table", 0.85, "Tableau (modele CALS)")]
    if node.kind == "section":
        return _section_candidates(ctx)
    if node.kind == "item-sequence":
        return _list_candidates(node, ctx)
    if node.kind == "item":
        # Resolu par son parent (listItem vs proceduralStep) ; pas de candidat propre.
        return []
    if node.kind == "paragraph":
        return _paragraph_candidates(ctx)
    return []


def resolve(root: IRNode) -> IRNode:
    """Attache les candidats + une confiance a chaque noeud de l'arbre.

    Mute l'IR en place et le renvoie. La confiance = score du meilleur candidat
    (proxy simple) ; les noeuds a plusieurs candidats proches sont signales
    low-confidence pour la revue humaine.
    """
    for node in root.walk():
        cands = candidates_for(node)
        if not cands:
            continue
        cands.sort(key=lambda c: c.score, reverse=True)
        node.candidates = cands
        node.confidence = cands[0].score
    return root
