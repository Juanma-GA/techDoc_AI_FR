"""Construction de l'IR a partir des blocs bruts d'un adapter.

Cette passe est purement STRUCTURELLE : elle pose la hierarchie (sections /
listes / admonitions / figures / tables / paragraphes) et la FORME de chaque
noeud, mais laisse `context` a "unknown" - c'est la classification IA en aval
(`context_classifier`) qui tranche descriptif vs procedural, ce qui determine
ensuite la balise S1000D (`resolver`).

Decoupe volontaire : la detection bas-niveau vit dans `structure_heuristics`,
ce module ne fait que l'assemblage de l'arbre.
"""

from __future__ import annotations

from app.core import structure_heuristics as heur
from app.core import zone_classifier
from app.core.ir import IRNode, RawBlock


class _Ids:
    """Generateur d'ids deterministe (n1, n2, ...). Deterministe = tests
    reproductibles et pas de Math.random/uuid dans la couche logique."""

    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return f"n{self._n}"


def build_ir(blocks: list[RawBlock]) -> IRNode:
    """Transforme une liste de blocs bruts en un arbre IR a racine unique."""
    ids = _Ids()
    zone_classifier.classify_zones(blocks)   # tague entetes/pieds (PDF)
    body_size = heur.body_font_size(blocks)
    root = IRNode(id=ids.next(), kind="section", text="", level=0)

    # Pile des sections ouvertes : (niveau, noeud). La racine est niveau 0.
    stack: list[tuple[int, IRNode]] = [(0, root)]
    pending_list: IRNode | None = None  # sequence d'items en cours d'accumulation

    def current() -> IRNode:
        return stack[-1][1]

    def close_list() -> None:
        nonlocal pending_list
        pending_list = None

    for block in blocks:
        text = (block.text or "").strip()
        if not text and not block.is_table:
            continue

        # 0) Entete / pied recurrent : court-circuite toute la cascade pour ne
        # PAS promouvoir un entete repete en titre (via infer_heading_level).
        # Garde comme paragraphe TAGGE : visible, hierarchisable, excluable.
        if block.zone in ("header", "footer", "cover", "toc"):
            close_list()
            current().children.append(
                IRNode(id=ids.next(), kind="paragraph", form="plain",
                       text=text, page=block.page, zone=block.zone, confidence=0.5)
            )
            continue

        # 1) Tableau -------------------------------------------------------
        rows = heur.to_table_rows(block)
        if rows is not None:
            close_list()
            current().children.append(
                IRNode(id=ids.next(), kind="table", form="table",
                       page=block.page, zone=block.zone, table_rows=rows,
                       table_header=block.table_header, confidence=0.6)
            )
            continue

        # 2) Legende de figure --------------------------------------------
        if heur.is_caption(text):
            close_list()
            current().children.append(
                IRNode(id=ids.next(), kind="figure", form="caption",
                       text=text, page=block.page, zone=block.zone,
                       refs=heur.detect_refs(text) or None, confidence=0.7)
            )
            continue

        # 3) Admonition (warning / caution / note) ------------------------
        adm = heur.detect_admonition(text)
        if adm is not None:
            close_list()
            current().children.append(
                IRNode(id=ids.next(), kind="admonition", admonition=adm,
                       form="plain", text=text, page=block.page, zone=block.zone,
                       refs=heur.detect_refs(text) or None, confidence=0.85)
            )
            continue

        # 4) Titre / section ----------------------------------------------
        level = block.heading_level or heur.infer_heading_level(block, body_size)
        if level is not None:
            close_list()
            # Remonter la pile jusqu'au parent de ce niveau.
            while len(stack) > 1 and stack[-1][0] >= level:
                stack.pop()
            section = IRNode(id=ids.next(), kind="section", form="subheading",
                             text=text, level=level, page=block.page, zone="chapter")
            current().children.append(section)
            stack.append((level, section))
            continue

        # 5) Item de liste -------------------------------------------------
        list_kind = block.list_kind or heur.detect_list_kind(text)
        if list_kind is not None:
            item_text = heur.strip_list_marker(text) if block.list_kind is None else text
            if pending_list is None or pending_list.form != list_kind:
                pending_list = IRNode(id=ids.next(), kind="item-sequence",
                                      form=list_kind, page=block.page,
                                      zone=block.zone, confidence=0.8)
                current().children.append(pending_list)
            pending_list.children.append(
                IRNode(id=ids.next(), kind="item", form=list_kind, text=item_text,
                       page=block.page, zone=block.zone,
                       refs=heur.detect_refs(item_text) or None)
            )
            continue

        # 6) Paragraphe ----------------------------------------------------
        close_list()
        current().children.append(
            IRNode(id=ids.next(), kind="paragraph", form="prose", text=text,
                   page=block.page, zone=block.zone,
                   refs=heur.detect_refs(text) or None)
        )

    return root
