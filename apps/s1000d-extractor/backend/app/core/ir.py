"""Modele logique canonique (IR) - le pivot de la migration.

L'IR est *independant de la source* (PDF spans, styles Word) ET *independant
de la cible* (vocabulaire S1000D d'une Issue donnee). C'est ce qui rend
l'outil generique : chaque adapter d'entree remplit le meme IR, et tout le
pipeline aval (classification de contexte, resolution d'elements, validation)
le consomme. On ne re-ecrit jamais de mapping par document.

Vocabulaire :
- `RawBlock` : unite brute produite par un adapter (texte + indices de forme).
- `IRNode`   : noeud de l'arbre logique normalise (contexte + forme + candidats).
- `Candidate`: une solution S1000D possible pour un noeud, avec score (cf. le
  cas "meme forme -> plusieurs balises selon le contexte").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# --- Vocabulaires controles --------------------------------------------------

# Forme visuelle observee dans le document source (signal *faible*).
Form = Literal["bullet", "ordered", "subheading", "prose", "plain", "table", "caption"]

# Contexte semantique S1000D (signal *fort*, decide par la classification IA).
Context = Literal["descriptive", "procedural", "unknown"]

# Zone de mise en page detectee (localisation du contenu dans la page source).
# `chapter` = titre de section ; `header`/`footer` = entete/pied recurrent (bruit
# a exclure) ; `body` = corps. Sert a hierarchiser et a filtrer le bruit.
Zone = Literal["header", "footer", "chapter", "cover", "toc", "body"]

# Nature logique du noeud (independante de la balise S1000D finale).
NodeKind = Literal[
    "section",         # un chapitre / une section avec un titre + des enfants
    "title",           # titre d'une section
    "paragraph",       # bloc de texte courant
    "item-sequence",   # une liste / sequence d'items (puces, numeros)
    "item",            # un item de sequence
    "admonition",      # warning / caution / note
    "figure",          # illustration + legende
    "table",           # tableau
]

Admonition = Literal["warning", "caution", "note"]


@dataclass
class RawBlock:
    """Bloc brut normalise par un adapter (pdf_parser / docx_parser).

    Les champs de forme sont des *indices* : l'adapter remplit ce qu'il sait
    (DOCX connait les styles donc `heading_level`/`list_kind` sont fiables ;
    le PDF doit les inferer via `font_size`/`bold`).
    """

    text: str
    page: int | None = None
    style_name: str | None = None       # ex. "Heading 1", "List Paragraph"
    font_size: float | None = None
    bold: bool = False
    heading_level: int | None = None    # 1..n si connu par l'adapter
    list_kind: Literal["bullet", "ordered"] | None = None
    list_level: int = 0
    is_table: bool = False
    table_rows: list[list[str]] | None = None
    table_header: list[str] | None = None      # ligne d'entete du tableau si connue
    # Geometrie (PDF uniquement) : coin haut/bas du bloc + hauteur de page, pour
    # detecter entetes/pieds. `None` cote DOCX/OCR (degradation gracieuse -> body).
    y0: float | None = None
    y1: float | None = None
    page_height: float | None = None
    zone: Zone = "body"
    image_xref: int | None = None              # xref PyMuPDF si le bloc est une image
    refs: list[dict] | None = None             # renvois/hyperliens detectes


@dataclass
class Candidate:
    """Une cible S1000D possible pour un noeud, avec sa justification.

    Plusieurs candidats = ambiguite assumee (ex. para vs proceduralStep) que
    l'humain tranchera. Le premier candidat (score le plus haut) est celui que
    le serialiseur emet par defaut ; les autres deviennent des commentaires
    `<!-- alt: ... -->`.
    """

    element: str
    score: float
    rationale: str = ""


def _empty_candidates() -> list[Candidate]:
    return []


def _empty_children() -> list[IRNode]:
    return []


@dataclass
class IRNode:
    id: str
    kind: NodeKind
    text: str = ""
    context: Context = "unknown"
    form: Form = "plain"
    admonition: Admonition | None = None
    level: int | None = None
    page: int | None = None
    zone: Zone = "body"
    confidence: float = 1.0
    candidates: list[Candidate] = field(default_factory=_empty_candidates)
    children: list[IRNode] = field(default_factory=_empty_children)
    table_rows: list[list[str]] | None = None
    table_header: list[str] | None = None      # ligne d'entete (-> thead CALS)
    icn: str | None = None                     # nom de fichier illustration associee
    icns: list[str] = field(default_factory=list)  # plusieurs fichiers pour une figure composee
    refs: list[dict] | None = None             # renvois/hyperliens (-> internalRef...)

    def walk(self) -> list[IRNode]:
        """Parcours prefixe (self puis enfants) - pratique pour stats/tests."""
        out = [self]
        for child in self.children:
            out.extend(child.walk())
        return out


def from_dict(data: dict) -> IRNode:
    """Reconstruit un IRNode depuis sa forme dict (inverse de `to_dict`).

    Utilise par l'override humain : on recharge l'arbre stocke, on modifie le
    candidat retenu d'un noeud, puis on re-serialise.
    """
    return IRNode(
        id=data["id"],
        kind=data["kind"],
        text=data.get("text", ""),
        context=data.get("context", "unknown"),
        form=data.get("form", "plain"),
        admonition=data.get("admonition"),
        level=data.get("level"),
        page=data.get("page"),
        zone=data.get("zone", "body"),
        confidence=data.get("confidence", 1.0),
        candidates=[
            Candidate(c["element"], c.get("score", 0.0), c.get("rationale", ""))
            for c in data.get("candidates", [])
        ],
        children=[from_dict(c) for c in data.get("children", [])],
        table_rows=data.get("table_rows"),
        table_header=data.get("table_header"),
        icn=data.get("icn"),
        icns=list(data.get("icns", [])),
        refs=data.get("refs"),
    )


def find_node(root: IRNode, node_id: str) -> IRNode | None:
    for n in root.walk():
        if n.id == node_id:
            return n
    return None


def to_dict(node: IRNode) -> dict:
    """Serialise l'IR en dict JSON-able (pour la DB, le SSE et le frontend)."""
    return {
        "id": node.id,
        "kind": node.kind,
        "text": node.text,
        "context": node.context,
        "form": node.form,
        "admonition": node.admonition,
        "level": node.level,
        "page": node.page,
        "zone": node.zone,
        "confidence": round(node.confidence, 3),
        "candidates": [
            {"element": c.element, "score": round(c.score, 3), "rationale": c.rationale}
            for c in node.candidates
        ],
        "table_rows": node.table_rows,
        "table_header": node.table_header,
        "icn": node.icn,
        "icns": node.icns,
        "refs": node.refs,
        "children": [to_dict(c) for c in node.children],
    }
