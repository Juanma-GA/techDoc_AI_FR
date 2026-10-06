"""Run a `catalog_json` payload (built-in rules of a StandardVersion).

Textual entries (regex_flag, regex_replace, term_replace,
case_capitalize, accent_fix) are dispatched to small in-module helpers.
The `sentence_length` kind (longueur de phrase, non exprimable en regex) est
délégué à `style_checks.run()`. Les entrées structurelles vont à
`structural_checks.run()`.

Ce module est la source unique des règles catalogue (l'ancien
`s1000d_checks.run()` a été retiré).
"""

from __future__ import annotations

import re
from typing import Any

from app.checks import structural_checks, style_checks
from app.checks.raw import RawSuggestion
from app.core.regex_safety import (
    USER_REGEX_TIMEOUT_SECONDS,
    UserRegexPatternError,
    compile_user_regex,
    mark_user_regex_incomplete,
)
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


TEXT_KINDS = {"regex_flag", "regex_replace", "term_replace", "case_capitalize", "accent_fix"}


def run(
    parsed: ParsedPdf,
    catalog: list[dict[str, Any]],
    warnings: list[str] | None = None,
) -> list[RawSuggestion]:
    out: list[RawSuggestion] = []
    out.extend(structural_checks.run(parsed, catalog, warnings=warnings))
    out.extend(_run_text(parsed.pages, catalog, warnings=warnings))
    for rule in catalog:
        if (rule.get("kind") or "").lower() == "sentence_length":
            out.extend(style_checks.run(parsed.pages, rule))
    return out


def _run_text(
    pages: list[ParsedPage],
    catalog: list[dict[str, Any]],
    warnings: list[str] | None = None,
) -> list[RawSuggestion]:
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
            compiled = compile_user_regex(pattern, flags)
        except UserRegexPatternError:
            mark_user_regex_incomplete(warnings)
            continue
        for page in pages:
            try:
                matches = list(
                    compiled.finditer(page.text or "", timeout=USER_REGEX_TIMEOUT_SECONDS)
                )
            except TimeoutError:
                mark_user_regex_incomplete(warnings)
                continue
            for m in matches:
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
