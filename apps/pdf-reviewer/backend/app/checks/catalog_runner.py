"""Run a `catalog_json` payload (built-in rules of a StandardVersion).

Textual entries (regex_flag, regex_replace, term_replace,
case_capitalize, accent_fix) are dispatched to small in-module helpers.
Structural entries are delegated to `structural_checks.run()`.

This module replaces the legacy `s1000d_checks.run()` for catalog-driven
analysis. The historic module stays around for backward compatibility
(its `RawSuggestion` dataclass is the shared transport type) but is no
longer the source of S1000D rules.
"""

from __future__ import annotations

import re
from typing import Any

from app.checks import structural_checks
from app.checks.s1000d_checks import RawSuggestion
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


TEXT_KINDS = {"regex_flag", "regex_replace", "term_replace", "case_capitalize", "accent_fix"}


def run(parsed: ParsedPdf, catalog: list[dict[str, Any]]) -> list[RawSuggestion]:
    out: list[RawSuggestion] = []
    out.extend(structural_checks.run(parsed, catalog))
    out.extend(_run_text(parsed.pages, catalog))
    return out


def _run_text(pages: list[ParsedPage], catalog: list[dict[str, Any]]) -> list[RawSuggestion]:
    out: list[RawSuggestion] = []
    for rule in catalog:
        kind = (rule.get("kind") or "").lower()
        if kind not in TEXT_KINDS:
            continue
        pattern = rule.get("pattern") or ""
        if not pattern:
            continue
        try:
            flags = re.IGNORECASE if kind in {"term_replace", "accent_fix"} else 0
            compiled = re.compile(pattern, flags)
        except re.error:
            continue
        for page in pages:
            for m in compiled.finditer(page.text or ""):
                original = m.group(0)
                proposed = _propose(kind, rule, m)
                out.append(
                    RawSuggestion(
                        rule_kind="standard",
                        rule_code=rule["code"],
                        severity=rule.get("severity") or "warning",
                        message=rule.get("message") or rule.get("title") or rule["code"],
                        original=original,
                        proposed=proposed,
                        page=page.page,
                        span=m.span(),
                    )
                )
    return out


def _propose(kind: str, rule: dict[str, Any], match: re.Match[str]) -> str:
    original = match.group(0)
    if kind == "regex_flag":
        return original
    if kind == "term_replace":
        return rule.get("replacement") or original
    if kind == "case_capitalize":
        if len(original) < 4:
            return original
        return original[0].upper() + original[1:].lower()
    if kind == "accent_fix":
        return rule.get("replacement") or original
    # regex_replace
    repl = rule.get("replacement") or ""
    try:
        return match.expand(repl) if repl else original
    except re.error:
        return repl or original
