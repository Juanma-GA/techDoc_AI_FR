"""Segmentation deterministe de la prose procedurale en etapes."""

from __future__ import annotations

import re
from collections.abc import Callable

from app.core import structure_heuristics as heur
from app.core.ir import IRNode, InlineRun

# Marqueurs de sequence FR + EN.
_SEQ_SPLIT = re.compile(
    r"(?:^|\.\s+|;\s+)(?=(?:first|second|third|then|next|after that|finally|"
    r"d'abord|ensuite|puis|enfin|apres)\b)",
    re.IGNORECASE,
)
_NUMBERED_ACTION_RE = re.compile(r"(?<!\S)(?P<number>\d{1,3})[.)]\s+")
_IMPERATIVE = re.compile(
    r"\b(remove|install|disconnect|connect|tighten|loosen|check|ensure|verify|"
    r"apply|set|turn|press|open|close|deposer|reposer|debrancher|brancher|serrer|"
    r"desserrer|verifier|appliquer|regler|ouvrir|fermer)\b",
    re.IGNORECASE,
)


def _split_numbered_actions(text: str) -> tuple[str, list[str]] | None:
    matches = list(_NUMBERED_ACTION_RE.finditer(text))
    numbers = [int(match.group("number")) for match in matches]
    if len(matches) < 2 or numbers != list(range(1, len(numbers) + 1)):
        return None

    intro = text[:matches[0].start()].rstrip()
    if not intro.endswith(":"):
        return None

    actions: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        action = text[match.end():end].strip(" \t\r\n;")
        if not action:
            return None
        actions.append(action)
    return intro, actions


def _heuristic_split(text: str) -> list[str]:
    parts = [p.strip(" .;") for p in _SEQ_SPLIT.split(text) if p.strip(" .;")]
    return parts if len(parts) >= 2 else []


def _looks_multi_action(text: str) -> bool:
    """Vrai si le paragraphe ressemble a plusieurs actions a decouper."""
    if _split_numbered_actions(text) is not None:
        return True
    sentences = [s for s in re.split(r"[.;]\s+", text) if len(s.strip()) > 3]
    verbs = len(_IMPERATIVE.findall(text))
    return len(sentences) >= 2 or verbs >= 2 or len(text) > 240


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
    runs: list[InlineRun],
    source_text: str,
    target_text: str,
) -> list[InlineRun]:
    if not runs or not target_text:
        return []
    run_text = "".join(run.text for run in runs)
    start = run_text.find(target_text)
    if start < 0:
        start = source_text.find(target_text)
    if start < 0:
        return [InlineRun(target_text)]
    return _slice_inline_runs(runs, start, start + len(target_text))


def _make_steps(node: IRNode, steps: list[str]) -> None:
    """Transforme un paragraphe en sequence d'items (etapes) low-confidence."""
    source_text = node.text
    source_runs = node.inline_runs
    node.kind = "item-sequence"
    node.form = "ordered"
    node.confidence = 0.4
    base = node.id
    node.text = ""
    node.children = [
        IRNode(
            id=f"{base}s{i}", kind="item", form="ordered", text=s,
            context=node.context, confidence=0.4,
            refs=heur.detect_refs(s) or None,
            inline_runs=_inline_runs_for_text(source_runs, source_text, s),
        )
        for i, s in enumerate(steps, start=1)
    ]
    node.refs = None
    node.inline_runs = []


def _make_numbered_action_group(
    node: IRNode,
    intro: str,
    actions: list[str],
) -> None:
    source_text = node.text
    source_runs = node.inline_runs
    base = node.id
    intro_node = IRNode(
        id=f"{base}-intro",
        kind="paragraph",
        text=intro,
        context="unknown",
        confidence=0.9,
        refs=heur.detect_refs(intro) or None,
        inline_runs=_inline_runs_for_text(source_runs, source_text, intro),
    )
    sequence = IRNode(
        id=f"{base}-steps",
        kind="item-sequence",
        form="ordered",
        context=node.context,
        confidence=0.4,
    )
    sequence.children = [
        IRNode(
            id=f"{base}-step-{index}",
            kind="item",
            form="ordered",
            text=action,
            context=node.context,
            confidence=0.4,
            refs=heur.detect_refs(action) or None,
            inline_runs=_inline_runs_for_text(source_runs, source_text, action),
        )
        for index, action in enumerate(actions, start=1)
    ]

    node.kind = "section"
    node.form = "subheading"
    node.text = ""
    node.confidence = 0.7
    node.refs = None
    node.inline_runs = []
    node.children = [intro_node, sequence]


def segment(
    root: IRNode,
    *,
    progress_cb: Callable[[int], None] | None = None,
) -> int:
    """Decoupe les paragraphes proceduraux en etapes. Renvoie le nb de splits.

    `progress_cb(pct)` (optionnel) est appele entre 60 et 74 pour faire avancer
    la barre pendant l'analyse des paragraphes candidats.
    """
    # Cibles : paragraphes proceduraux qui ressemblent a plusieurs actions.
    targets = [
        n for n in root.walk()
        if n.kind == "paragraph" and n.context == "procedural"
        and (
            _split_numbered_actions(n.text) is not None
            or (len(n.text) >= 60 and _looks_multi_action(n.text))
        )
    ]

    count = 0
    for i, node in enumerate(targets):
        numbered = _split_numbered_actions(node.text)
        if numbered is not None:
            _make_numbered_action_group(node, *numbered)
            count += 1
        else:
            steps = _heuristic_split(node.text)
            if steps:
                _make_steps(node, steps)
                count += 1
        if progress_cb and targets:
            progress_cb(60 + int(14 * (i + 1) / len(targets)))
    return count
