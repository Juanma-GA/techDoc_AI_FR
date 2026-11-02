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

import re
from collections.abc import Callable

from app.core import structure_heuristics as heur
from app.core import zone_classifier
from app.core.ir import InlineRun, IRNode, RawBlock
from app.core.progress import progress_items

_NUMBERED_NOTE_ITEM_RE = re.compile(r"(?m)(?<!\S)(?P<number>\d{1,3})[.)][ \t]+")
_ORDERED_ITEM_NUMBER_RE = re.compile(r"^\s*(?P<number>\d{1,3})[.)]\s+")
_LINE_LIST_ITEM_RE = re.compile(r"(?m)^[ \t]*(?P<marker>\d{1,3}[.)]|[a-z][.)])[ \t]+", re.IGNORECASE)


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


def _clean_item_text(text: str) -> str:
    return re.sub(r"^[\s\x00-\x1f]+", "", text).strip()


def _inline_runs_without_controls(runs: list[InlineRun]) -> list[InlineRun]:
    cleaned: list[InlineRun] = []
    for run in runs:
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", run.text)
        if text:
            cleaned.append(InlineRun(
                text=text,
                bold=run.bold,
                italic=run.italic,
                underline=run.underline,
                overline=run.overline,
                strikethrough=run.strikethrough,
            ))
    return cleaned


def _split_numbered_note_items(text: str) -> tuple[str, list[str]] | None:
    matches = list(_NUMBERED_NOTE_ITEM_RE.finditer(text))
    numbers = [int(match.group("number")) for match in matches]
    if not matches or numbers != list(range(1, len(matches) + 1)):
        return None

    intro = text[:matches[0].start()].rstrip()
    items = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        item = _clean_item_text(text[match.end():end].strip(" \t\r\n;"))
        if not item:
            return None
        items.append(item)
    return intro, items


def _ordered_item_number(text: str) -> int | None:
    match = _ORDERED_ITEM_NUMBER_RE.match(text)
    return int(match.group("number")) if match else None


def _split_inline_list_block(
    block: RawBlock,
    ids: _Ids,
) -> tuple[str, list[IRNode]] | None:
    matches = list(_LINE_LIST_ITEM_RE.finditer(block.text))
    if len(matches) < 2:
        return None

    prefix = block.text[:matches[0].start()].strip()
    sequences: list[IRNode] = []
    active_sequence: IRNode | None = None
    last_numbered_item: IRNode | None = None
    nested_lettered_sequence: IRNode | None = None

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(block.text)
        raw_item_text = block.text[match.end():end].strip(" \t\r\n")
        item_text = _clean_item_text(raw_item_text)
        if not item_text:
            return None
        item_runs = _inline_runs_without_controls(
            _inline_runs_for_text(block.inline_runs, block.text, raw_item_text)
        )
        marker = match.group("marker")

        if marker[0].isdigit():
            if active_sequence is None or active_sequence.form != "ordered":
                active_sequence = IRNode(
                    id=ids.next(), kind="item-sequence", form="ordered",
                    page=block.page, zone=block.zone, confidence=0.8,
                )
                sequences.append(active_sequence)
            item = IRNode(
                id=ids.next(), kind="item", form="ordered", text=item_text,
                page=block.page, zone=block.zone,
                refs=heur.detect_refs(item_text) or None,
                inline_runs=item_runs,
            )
            active_sequence.children.append(item)
            last_numbered_item = item
            nested_lettered_sequence = None
            continue

        if last_numbered_item is not None:
            if nested_lettered_sequence is None:
                nested_lettered_sequence = IRNode(
                    id=ids.next(), kind="item-sequence", form="lettered",
                    page=block.page, zone=block.zone, confidence=0.8,
                )
                last_numbered_item.children.append(nested_lettered_sequence)
            lettered_sequence = nested_lettered_sequence
        else:
            if active_sequence is None or active_sequence.form != "lettered":
                active_sequence = IRNode(
                    id=ids.next(), kind="item-sequence", form="lettered",
                    page=block.page, zone=block.zone, confidence=0.8,
                )
                sequences.append(active_sequence)
            lettered_sequence = active_sequence

        lettered_text = f"{marker} {item_text}"
        lettered_runs = [InlineRun(f"{marker} "), *item_runs]
        lettered_sequence.children.append(
            IRNode(
                id=ids.next(), kind="item", form="lettered", text=lettered_text,
                page=block.page, zone=block.zone,
                refs=heur.detect_refs(item_text) or None,
                inline_runs=lettered_runs,
            )
        )

    return prefix, sequences


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
    if previous.zone != current.zone or previous.zone != "body":
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


def build_ir(
    blocks: list[RawBlock], *, progress_cb: Callable[[int, int], None] | None = None,
) -> IRNode:
    """Transforme une liste de blocs bruts en un arbre IR a racine unique."""
    zone_classifier.classify_zones(blocks)   # tague les zones avant toute fusion
    blocks = _merge_touching_continuation(blocks)
    ids = _Ids()
    body_size = heur.body_font_size(blocks)
    root = IRNode(id=ids.next(), kind="section", text="", level=0)

    # Pile des sections ouvertes : (niveau, noeud). La racine est niveau 0.
    stack: list[tuple[int, IRNode]] = [(0, root)]
    pending_list: IRNode | None = None  # sequence d'items en cours d'accumulation
    pending_list_parent: IRNode | None = None
    pending_attention: IRNode | None = None
    pending_attention_list: IRNode | None = None
    pending_attention_number = 1

    def current() -> IRNode:
        return stack[-1][1]

    def close_list() -> None:
        nonlocal pending_list, pending_list_parent
        pending_list = None
        pending_list_parent = None

    def close_attention() -> None:
        nonlocal pending_attention, pending_attention_list, pending_attention_number
        pending_attention = None
        pending_attention_list = None
        pending_attention_number = 1

    for block in progress_items(blocks, progress_cb):
        text = (block.text or "").strip()
        if not text and not block.is_table:
            continue

        layout_zone = block.zone in ("header", "footer", "cover", "toc")
        if pending_attention is not None and not layout_zone:
            if not heur.is_caption(text):
                if _ordered_item_number(text) == pending_attention_number:
                    if pending_attention_list is None:
                        pending_attention_list = IRNode(
                            id=ids.next(), kind="item-sequence", form="ordered",
                            page=block.page, zone=block.zone, confidence=0.8,
                        )
                        pending_attention.children.append(pending_attention_list)
                    raw_item_text = heur.strip_list_marker(text)
                    item_text = _clean_item_text(raw_item_text)
                    item_runs = _inline_runs_without_controls(
                        _inline_runs_for_text(block.inline_runs, block.text, raw_item_text)
                    )
                    pending_attention_list.children.append(
                        IRNode(
                            id=ids.next(), kind="item", form="ordered", text=item_text,
                            page=block.page, zone=block.zone,
                            refs=heur.detect_refs(item_text) or None,
                            inline_runs=item_runs,
                        )
                    )
                    pending_attention_number += 1
                    close_list()
                    continue
                close_attention()

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
        confidence = 0.85
        rationale = "Marqueur textuel d'admonition detecte."
        if adm is None and block.is_pictogram:
            adm, confidence, rationale = heur.classify_callout(text, pictogram=True)
        if adm is not None:
            close_list()
            note_text = text
            note_items = _split_numbered_note_items(text) if adm == "note" else None
            if note_items is not None:
                note_text, item_texts = note_items
            else:
                item_texts = []
            note = IRNode(
                id=ids.next(), kind="admonition", admonition=adm,
                form="plain", text=note_text, page=block.page, zone=block.zone,
                refs=heur.detect_refs(note_text) or None, confidence=confidence,
                admonition_rationale=rationale,
                is_pictogram=block.is_pictogram,
                inline_runs=_inline_runs_for_text(block.inline_runs, block.text, note_text),
            )
            if adm == "note" and (item_texts or note_text.rstrip().endswith(":")):
                pending_attention = note
                pending_attention_number = len(item_texts) + 1
                pending_attention_list = None
                if item_texts:
                    pending_attention_list = IRNode(
                        id=ids.next(), kind="item-sequence", form="ordered",
                        page=block.page, zone=block.zone, confidence=0.8,
                    )
                    pending_attention_list.children = [
                        IRNode(
                            id=ids.next(), kind="item", form="ordered", text=item_text,
                            page=block.page, zone=block.zone,
                            refs=heur.detect_refs(item_text) or None,
                            inline_runs=_inline_runs_without_controls(
                                _inline_runs_for_text(block.inline_runs, block.text, item_text)
                            ),
                        )
                        for item_text in item_texts
                    ]
                    note.children.append(pending_attention_list)
            current().children.append(note)
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

        # 5) Listes multi-items dans un meme bloc PDF --------------------
        split_list = _split_inline_list_block(block, ids)
        if split_list is not None:
            prefix, sequences = split_list
            close_list()
            if prefix:
                current().children.append(
                    IRNode(
                        id=ids.next(), kind="paragraph", form="prose", text=prefix,
                        page=block.page, zone=block.zone,
                        refs=heur.detect_refs(prefix) or None,
                        inline_runs=_inline_runs_for_text(block.inline_runs, block.text, prefix),
                    )
                )
            current().children.extend(sequences)
            pending_list = sequences[-1] if sequences else None
            continue

        # 6) Item de liste -------------------------------------------------
        marker_match = _LINE_LIST_ITEM_RE.match(text)
        marker_kind = (
            "lettered"
            if marker_match is not None and not marker_match.group("marker")[0].isdigit()
            else None
        )
        list_kind = block.list_kind or marker_kind or heur.detect_list_kind(text)
        if list_kind is not None:
            if list_kind == "lettered":
                marker_match = _LINE_LIST_ITEM_RE.match(text)
                marker = marker_match.group("marker") if marker_match else ""
                raw_item_text = heur.strip_list_marker(text)
                item_text = f"{marker} {_clean_item_text(raw_item_text)}".strip()
                item_runs = [InlineRun(f"{marker} ")] + _inline_runs_without_controls(
                    _inline_runs_for_text(block.inline_runs, block.text, raw_item_text)
                )
            else:
                raw_item_text = heur.strip_list_marker(text) if block.list_kind is None else text
                item_text = _clean_item_text(raw_item_text)
                item_runs = _inline_runs_without_controls(
                    _inline_runs_for_text(block.inline_runs, block.text, raw_item_text)
                )
            if list_kind == "ordered" and pending_list_parent is not None:
                pending_list = pending_list_parent
                pending_list_parent = None
            if pending_list is None or pending_list.form != list_kind:
                sequence = IRNode(
                    id=ids.next(), kind="item-sequence", form=list_kind,
                    page=block.page, zone=block.zone, confidence=0.8,
                )
                if (
                    list_kind == "lettered"
                    and pending_list is not None
                    and pending_list.form == "ordered"
                    and pending_list.children
                ):
                    pending_list_parent = pending_list
                    pending_list.children[-1].children.append(sequence)
                else:
                    current().children.append(sequence)
                pending_list = sequence
            pending_list.children.append(
                IRNode(id=ids.next(), kind="item", form=list_kind, text=item_text,
                       page=block.page, zone=block.zone,
                       refs=heur.detect_refs(item_text) or None,
                      inline_runs=item_runs)
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
