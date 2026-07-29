"""Structural checks for documentation standards.

Each rule kind detected here works at the *document* level, not the
*text* level — there is no replacement to propose, so the suggestions
emitted are detection-only (`proposed == original`). The reviewer UI
shows them as warnings the human has to act on manually (edit the source
document).

Supported kinds:

- `field_required`     — a labelled field must appear at least once.
- `section_required`   — a section title must appear at least once.
- `field_consistency`  — correlate two fields (task vs spare part…).
- `step_pattern`       — every procedure step matches a regex.
- `enum_value`         — a labelled field's value belongs to an enum.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from app.checks.raw import RawSuggestion
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


STRUCTURAL_KINDS = {
    "field_required",
    "section_required",
    "field_consistency",
    "step_pattern",
    "enum_value",
}


def run(parsed: ParsedPdf, catalog: list[dict[str, Any]]) -> list[RawSuggestion]:
    """Execute every structural rule from `catalog` against the full doc."""
    out: list[RawSuggestion] = []
    full_text = parsed.full_text or ""
    first_page = parsed.pages[0].page if parsed.pages else 1
    for rule in catalog:
        kind = (rule.get("kind") or "").lower()
        if kind not in STRUCTURAL_KINDS:
            continue
        if kind == "field_required":
            out.extend(_field_required(rule, full_text, first_page))
        elif kind == "section_required":
            out.extend(_section_required(rule, full_text, first_page))
        elif kind == "field_consistency":
            out.extend(_field_consistency(rule, full_text, first_page))
        elif kind == "step_pattern":
            out.extend(_step_pattern(rule, parsed.pages))
        elif kind == "enum_value":
            out.extend(_enum_value(rule, full_text, first_page))
    return out


def _emit(rule: dict[str, Any], page: int, original: str = "") -> RawSuggestion:
    """Structural rules are *detection-only* — they signal a problem but
    don't propose a verbatim replacement (a missing section can't be
    auto-inserted from a regex). We emit `proposed=""` so the UI knows
    not to display a misleading « X → X » diff arrow and to disable the
    `Apply` button for these suggestions."""
    return RawSuggestion(
        rule_kind="standard",
        rule_code=rule["code"],
        severity=rule.get("severity") or "warning",
        message=rule.get("message") or rule.get("title") or rule["code"],
        original=original,
        proposed="",
        page=page,
        span=(0, len(original)),
    )


_LABEL_SEPARATOR = re.compile(r"\s*[:=]\s*")


def _labels(pattern: str) -> list[str]:
    """`Périodicité|Periodicity` → ['Périodicité', 'Periodicity']."""
    return [s.strip() for s in pattern.split("|") if s.strip()]


def _field_required(rule: dict[str, Any], text: str, page: int) -> Iterable[RawSuggestion]:
    labels = _labels(rule.get("pattern", ""))
    if not labels:
        return
    if any(re.search(rf"\b{re.escape(lbl)}\b", text, re.IGNORECASE) for lbl in labels):
        return
    yield _emit(rule, page, original=labels[0])


def _section_required(rule: dict[str, Any], text: str, page: int) -> Iterable[RawSuggestion]:
    yield from _field_required(rule, text, page)


def _step_pattern(rule: dict[str, Any], pages: list[ParsedPage]) -> Iterable[RawSuggestion]:
    """Flag procedure steps that don't match the required pattern.

    A step is a line beginning with an **explicit ordinal** (`1.`, `2)`,
    `(1)`, `1]`, `Step 1.` etc.) — not a bulleted list item. Bullet
    points (`-`, `•`, `*`) frequently mark section/field labels in
    technical documents (« • Applicabilité », « • Référence ») and
    flagging them as procedural steps produced very noisy false
    positives, so they're now excluded.

    Additionally, step bodies that look like a field label (a single
    capitalized word with no verb, ≤ 25 characters) are silently
    skipped — those are picked up by `section_required` /
    `field_required` rules anyway."""
    pattern = rule.get("pattern", "")
    if not pattern:
        return
    try:
        verb_re = re.compile(pattern)
    except re.error:
        return
    # Numbered list markers only. Captures: "1.", "1)", "(1)", "1]",
    # "Step 1.", "Étape 1.". No bullets / dashes.
    step_re = re.compile(
        r"^\s*(?:(?:Step|Étape|Etape)\s+)?\(?\d+[.)\]]\s+(.+)$",
        re.MULTILINE,
    )
    for page in pages:
        for m in step_re.finditer(page.text or ""):
            step_body = m.group(1).strip()
            if not step_body:
                continue
            if verb_re.match(step_body):
                continue
            if _looks_like_field_label(step_body):
                # Single short capitalised word → handled by other rules.
                continue
            preview = step_body if len(step_body) <= 160 else step_body[:160] + "…"
            yield _emit(rule, page.page, original=preview)


_LABEL_LIKE_RE = re.compile(r"^[A-ZÀ-Ÿ][\w'’\-\sÀ-ÿ]{0,24}[\s:]*$")


def _looks_like_field_label(text: str) -> bool:
    """Heuristic: a capitalised noun (single word or short noun phrase
    ≤ 25 chars, no terminal punctuation) is almost certainly a field
    label, not a procedural step."""
    if len(text) > 25:
        return False
    if any(text.rstrip(": ").endswith(p) for p in (".", "!", "?")):
        return False
    return bool(_LABEL_LIKE_RE.match(text))


def _enum_value(rule: dict[str, Any], text: str, page: int) -> Iterable[RawSuggestion]:
    """Find the labelled field and check its value is in the enum.

    `metadata.field_label` overrides the label scanned (defaults to the
    rule title). `pattern` is the comma-separated enum."""
    label = (rule.get("metadata") or {}).get("field_label") or rule.get("title") or ""
    if not label:
        return
    accepted = {v.strip().lower() for v in (rule.get("pattern") or "").split(",") if v.strip()}
    if not accepted:
        return
    needle = re.compile(rf"{re.escape(label)}\s*[:=]\s*([^\n\r]{{1,80}})", re.IGNORECASE)
    match = needle.search(text)
    if match is None:
        yield _emit(rule, page, original=label)
        return
    value = _LABEL_SEPARATOR.sub("", match.group(1).strip()).split()[0].lower()
    if value not in accepted:
        yield _emit(rule, page, original=match.group(1).strip())


def _field_consistency(
    rule: dict[str, Any],
    text: str,
    page: int,
) -> Iterable[RawSuggestion]:
    """Cross-field consistency check.

    Pattern syntax: `task=kw1|kw2;spare=kw3|kw4`. If a task keyword
    appears in the document but none of the spare keywords do, emit a
    warning."""
    pattern = rule.get("pattern", "")
    parts = dict(_parse_consistency(pattern))
    task_keywords = [k.strip().lower() for k in parts.get("task", "").split("|") if k.strip()]
    spare_keywords = [k.strip().lower() for k in parts.get("spare", "").split("|") if k.strip()]
    if not task_keywords or not spare_keywords:
        return
    low = text.lower()
    if not any(k in low for k in task_keywords):
        return  # rule does not apply (no replace/install task)
    if any(k in low for k in spare_keywords):
        return  # ok
    yield _emit(rule, page, original=task_keywords[0])


def _parse_consistency(expr: str) -> Iterable[tuple[str, str]]:
    for chunk in expr.split(";"):
        if "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        yield k.strip(), v.strip()
