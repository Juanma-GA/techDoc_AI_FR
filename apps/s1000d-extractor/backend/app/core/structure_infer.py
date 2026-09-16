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
from app.core.ir import IRNode, InlineRun, RawBlock


class _Ids:
    """Generateur d'ids deterministe (n1, n2, ...). Deterministe = tests
    reproductibles et pas de Math.random/uuid dans la couche logique."""

    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return f"n{self._n}"


def _slice_inline_runs(runs: list[InlineRun], start: int, end: int) -> list[InlineRun]:
    selected: list[InlineRun] = []
    position = 0
    for run in runs:
        run_end = position + len(run.text)
        left = max(start, position)
        right = min(end, run_end)
        if left < right:
            selected.append(InlineRun(
                text=run.text[left - position:right - position],
                bold=run.bold,
                italic=run.italic,
                underline=run.underline,
                overline=run.overline,
                strikethrough=run.strikethrough,
            ))
        position = run_end
        if position >= end:
            break
    return selected


def _inline_runs_for_text(
    runs: list[InlineRun], source_text: str, target_text: str
) -> list[InlineRun]:
    if not runs or not target_text:
        return []
    source = "".join(run.text for run in runs)
    start = source.find(target_text)
    if start < 0:
        return [InlineRun(target_text)]
    return _slice_inline_runs(runs, start, start + len(target_text))


def _merge_touching_continuation(blocks: list[RawBlock]) -> list[RawBlock]:
    """Recolle un bloc PDF qui continue exactement le bloc precedent."""
    merged: list[RawBlock] = []
    for block in blocks:
        if merged and _is_touching_continuation(merged[-1], block):
            previous = merged[-1]
            previous_text = previous.text
            current_text = block.text
            previous_trimmed = previous_text.rstrip()
            current_trimmed = current_text.lstrip()
            previous.text = f"{previous_trimmed} {current_trimmed}"
            previous_runs = _inline_runs_for_text(
                previous.inline_runs, previous_text, previous_trimmed
            ) or [InlineRun(previous_trimmed)]
            current_runs = _inline_runs_for_text(
                block.inline_runs, current_text, current_trimmed
            ) or [InlineRun(current_trimmed)]
            previous.inline_runs = (
                previous_runs
                + [InlineRun(" ")]
                + current_runs
            )
            previous.y1 = block.y1
            continue
        merged.append(block)
    return merged


def _is_touching_continuation(previous: RawBlock, current: RawBlock) -> bool:
    if previous.page != current.page or previous.is_table or current.is_table:
        return False
    if previous.y1 is None or current.y0 is None:
        return False
    if current.y0 - previous.y1 > 2.0:
        return False
    text = current.text.lstrip()
    if heur.detect_list_kind(text) is not None:
        return False
    if text.startswith(("•", "·", "‣", "◦", "⁃", "∙", "-", "–", "—", "*")):
        return False
    return True


def build_ir(blocks: list[RawBlock]) -> IRNode:
    """Transforme une liste de blocs bruts en un arbre IR a racine unique."""
    blocks = _merge_touching_continuation(blocks)
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
                      text=text, page=block.page, zone=block.zone, confidence=0.5,
                      inline_runs=_inline_runs_for_text(block.inline_runs, block.text, text))
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
            for caption in heur.split_captions(text):
                current().children.append(
                    IRNode(id=ids.next(), kind="figure", form="caption",
                           text=caption, page=block.page, zone=block.zone,
                               refs=heur.detect_refs(caption) or None, confidence=0.7,
                               inline_runs=_inline_runs_for_text(block.inline_runs, block.text, caption))
                )
            continue

        # 3) Admonition (warning / caution / note) ------------------------
        adm = heur.detect_admonition(text)
        if adm is not None:
            close_list()
            current().children.append(
                IRNode(id=ids.next(), kind="admonition", admonition=adm,
                       form="plain", text=text, page=block.page, zone=block.zone,
                      refs=heur.detect_refs(text) or None, confidence=0.85,
                      inline_runs=_inline_runs_for_text(block.inline_runs, block.text, text))
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
                             text=text, level=level, page=block.page, zone="chapter",
                             inline_runs=_inline_runs_for_text(block.inline_runs, block.text, text))
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
                       refs=heur.detect_refs(item_text) or None,
                       inline_runs=_inline_runs_for_text(block.inline_runs, text, item_text))
            )
            continue

        # 6) Paragraphe ----------------------------------------------------
        close_list()
        current().children.append(
            IRNode(id=ids.next(), kind="paragraph", form="prose", text=text,
                   page=block.page, zone=block.zone,
                   refs=heur.detect_refs(text) or None,
                   inline_runs=_inline_runs_for_text(block.inline_runs, block.text, text))
        )

    return root
