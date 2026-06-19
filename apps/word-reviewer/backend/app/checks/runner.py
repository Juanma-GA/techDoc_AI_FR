"""Execution d'une liste de regles normalisees sur un `ParsedDocx`.

Une regle normalisee est un dict :
  {code, kind, severity, message, pattern, replacement, target_zone,
   metadata, rule_kind, rule_id, title}

Les regles builtin (catalogue StandardVersion) et custom (table Rule) sont
toutes converties a cette forme par `rules_engine`, puis dispatchees ici par
`kind`. `llm_nl` est ignore (traite par le module LLM). `manual` produit un
item informatif a cocher.
"""

from __future__ import annotations

import re
from typing import Any

from app.checks import revision_checks
from app.checks.raw import RawSuggestion
from app.parsers.docx_parser import Block, ParsedDocx


TEXT_KINDS = {"regex_flag", "regex_replace", "term_replace", "case_capitalize", "accent_fix"}
STRUCTURAL_KINDS = {"field_required", "section_required", "field_consistency", "step_pattern", "enum_value"}


def run(parsed: ParsedDocx, rules: list[dict[str, Any]]) -> list[RawSuggestion]:
    out: list[RawSuggestion] = []
    for rule in rules:
        kind = (rule.get("kind") or "").lower()
        if kind in TEXT_KINDS:
            out.extend(_run_text(parsed, rule))
        elif kind in STRUCTURAL_KINDS:
            out.extend(_run_structural(parsed, rule))
        elif kind == "style_check":
            out.extend(_run_style(parsed, rule))
        elif kind == "zone_field":
            out.extend(_run_zone_field(parsed, rule))
        elif kind == "revision_check":
            out.extend(revision_checks.run(parsed, rule))
        elif kind == "manual":
            out.append(_emit_manual(rule))
        # llm_nl : ignore ici (cf. app.core.llm_checks)
    return out


# --------------------------------------------------------------------------- #
# Helpers d'emission
# --------------------------------------------------------------------------- #


def _base(rule: dict[str, Any], **kw: Any) -> RawSuggestion:
    return RawSuggestion(
        rule_kind=str(rule.get("rule_kind", "standard")),
        rule_code=str(rule["code"]),
        severity=str(rule.get("severity") or "warning"),
        message=str(rule.get("message") or rule.get("title") or rule["code"]),
        rule_id=rule.get("rule_id"),
        **kw,
    )


def _zone_blocks(parsed: ParsedDocx, zone: str) -> list[Block]:
    return [b for b in parsed.blocks if b.semantic_zone == zone or b.zone == zone]


def _target_filter(parsed: ParsedDocx, rule: dict[str, Any]) -> list[Block]:
    tz = (rule.get("target_zone") or "").strip()
    if tz:
        return _zone_blocks(parsed, tz)
    return list(parsed.blocks)


# --------------------------------------------------------------------------- #
# Texte (regex)
# --------------------------------------------------------------------------- #


def _run_text(parsed: ParsedDocx, rule: dict[str, Any]) -> list[RawSuggestion]:
    pattern = rule.get("pattern") or ""
    if not pattern:
        return []
    kind = rule["kind"].lower()
    flags = re.IGNORECASE if kind in {"term_replace", "accent_fix"} else 0
    try:
        compiled = re.compile(pattern, flags)
    except re.error:
        return []
    out: list[RawSuggestion] = []
    seen: dict[str, int] = {}
    for block in _target_filter(parsed, rule):
        if not block.text:
            continue
        for m in compiled.finditer(block.text):
            original = m.group(0)
            out.append(
                _base(
                    rule,
                    original=original,
                    proposed=_propose(kind, rule, m),
                    target_id=block.target_id,
                    block_index=block.index,
                    zone=block.zone,
                    semantic_zone=block.semantic_zone or "",
                    char_start=m.start(),
                    char_end=m.end(),
                )
            )
            seen[block.target_id] = seen.get(block.target_id, 0) + 1
    return out


def _propose(kind: str, rule: dict[str, Any], match: re.Match[str]) -> str:
    original = match.group(0)
    if kind == "regex_flag":
        return original
    if kind in {"term_replace", "accent_fix"}:
        return rule.get("replacement") or original
    if kind == "case_capitalize":
        return original if len(original) < 4 else original[0].upper() + original[1:].lower()
    repl = rule.get("replacement") or ""  # regex_replace
    try:
        return match.expand(repl) if repl else original
    except re.error:
        return repl or original


# --------------------------------------------------------------------------- #
# Structurel (presence / coherence / enum / steps)
# --------------------------------------------------------------------------- #


def _labels(pattern: str) -> list[str]:
    return [s.strip() for s in pattern.split("|") if s.strip()]


def _first_target(parsed: ParsedDocx, rule: dict[str, Any]) -> Block | None:
    blocks = _target_filter(parsed, rule)
    return blocks[0] if blocks else None


def _run_structural(parsed: ParsedDocx, rule: dict[str, Any]) -> list[RawSuggestion]:
    kind = rule["kind"].lower()
    text = parsed.full_text or ""
    if kind in {"field_required", "section_required"}:
        labels = _labels(rule.get("pattern", ""))
        if labels and not any(
            re.search(rf"\b{re.escape(lbl)}\b", text, re.IGNORECASE) for lbl in labels
        ):
            return [_base(rule, original=labels[0], proposed="")]
        return []
    if kind == "enum_value":
        return _enum_value(parsed, rule, text)
    if kind == "field_consistency":
        return _field_consistency(rule, text)
    if kind == "step_pattern":
        return _step_pattern(parsed, rule)
    return []


def _enum_value(parsed: ParsedDocx, rule: dict[str, Any], text: str) -> list[RawSuggestion]:
    label = (rule.get("metadata") or {}).get("field_label") or rule.get("title") or ""
    accepted = {v.strip().lower() for v in (rule.get("pattern") or "").split(",") if v.strip()}
    if not label or not accepted:
        return []
    m = re.search(rf"{re.escape(label)}\s*[:=]\s*([^\n\r]{{1,80}})", text, re.IGNORECASE)
    if m is None:
        return [_base(rule, original=label, proposed="")]
    value = re.sub(r"\s*[:=]\s*", "", m.group(1).strip()).split()
    if value and value[0].lower() not in accepted:
        return [_base(rule, original=m.group(1).strip(), proposed="")]
    return []


def _field_consistency(rule: dict[str, Any], text: str) -> list[RawSuggestion]:
    parts: dict[str, str] = {}
    for chunk in (rule.get("pattern") or "").split(";"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.strip()] = v.strip()
    task = [k.strip().lower() for k in parts.get("task", "").split("|") if k.strip()]
    spare = [k.strip().lower() for k in parts.get("spare", "").split("|") if k.strip()]
    if not task or not spare:
        return []
    low = text.lower()
    if any(k in low for k in task) and not any(k in low for k in spare):
        return [_base(rule, original=task[0], proposed="")]
    return []


_STEP_RE = re.compile(r"^\s*(?:(?:Step|Etape|Etape)\s+)?\(?\d+[.)\]]\s+(.+)$", re.MULTILINE)


def _step_pattern(parsed: ParsedDocx, rule: dict[str, Any]) -> list[RawSuggestion]:
    pattern = rule.get("pattern", "")
    if not pattern:
        return []
    try:
        verb_re = re.compile(pattern)
    except re.error:
        return []
    out: list[RawSuggestion] = []
    for block in parsed.blocks:
        for m in _STEP_RE.finditer(block.text or ""):
            body = m.group(1).strip()
            if not body or verb_re.match(body):
                continue
            out.append(
                _base(
                    rule,
                    original=body[:160],
                    proposed="",
                    target_id=block.target_id,
                    block_index=block.index,
                    zone=block.zone,
                    semantic_zone=block.semantic_zone or "",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# Style (alignement) + Zone (footer/header...)
# --------------------------------------------------------------------------- #


def _run_style(parsed: ParsedDocx, rule: dict[str, Any]) -> list[RawSuggestion]:
    meta = rule.get("metadata") or {}
    want = (meta.get("align") or "justify").lower()
    try:
        min_len = int(meta.get("min_len", "40"))
    except (TypeError, ValueError):
        min_len = 40
    out: list[RawSuggestion] = []
    for block in _target_filter(parsed, rule):
        if block.kind != "paragraph" or len(block.text.strip()) < min_len:
            continue
        if block.alignment is not None and block.alignment != want:
            out.append(
                _base(
                    rule,
                    original=block.text[:120],
                    proposed="",
                    target_id=block.target_id,
                    block_index=block.index,
                    zone=block.zone,
                    semantic_zone=block.semantic_zone or "",
                )
            )
    return out


def _run_zone_field(parsed: ParsedDocx, rule: dict[str, Any]) -> list[RawSuggestion]:
    meta = rule.get("metadata") or {}
    zone = rule.get("target_zone") or meta.get("zone") or "body"
    mode = (meta.get("mode") or "require").lower()
    pattern = rule.get("pattern") or ""
    if not pattern:
        return []
    try:
        compiled = re.compile(pattern)
    except re.error:
        return []
    blocks = _zone_blocks(parsed, zone)
    if not blocks:
        # Zone non reconnue dans ce document : on retombe sur tout le corps
        # plutot que de signaler a tort « absent » (faux positif).
        blocks = parsed.blocks
    zone_text = "\n".join(b.text for b in blocks)
    out: list[RawSuggestion] = []
    if mode == "forbid":
        for block in blocks:
            for m in compiled.finditer(block.text or ""):
                out.append(
                    _base(
                        rule,
                        original=m.group(0),
                        proposed=rule.get("replacement", ""),
                        target_id=block.target_id,
                        block_index=block.index,
                        zone=block.zone,
                        semantic_zone=block.semantic_zone or zone,
                        char_start=m.start(),
                        char_end=m.end(),
                    )
                )
    else:  # require
        if not compiled.search(zone_text):
            first = blocks[0] if blocks else None
            out.append(
                _base(
                    rule,
                    original=str(meta.get("label") or ""),
                    proposed="",
                    target_id=first.target_id if first else "",
                    block_index=first.index if first else 0,
                    zone=first.zone if first else "body",
                    semantic_zone=zone,
                )
            )
    return out


def _emit_manual(rule: dict[str, Any]) -> RawSuggestion:
    return _base(
        rule,
        original="",
        proposed="",
        semantic_zone=str((rule.get("metadata") or {}).get("zone", "")),
    )
