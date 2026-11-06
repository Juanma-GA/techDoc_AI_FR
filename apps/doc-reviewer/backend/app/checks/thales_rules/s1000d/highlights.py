"""S1000D HIGHLIGHTS reason-for-update checks."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.checks.client_bundle import ClientOperation, OperationResult
from app.parsers.pdf_parser import ParsedPage, ParsedPdf

from .data_modules import (
    DMC_RE,
    STATUS_CHANGED,
    STATUS_REVISED,
    complete_pages,
    parse_loedm,
    unwrap_dmc,
)

RFU_RE = re.compile(r"(?i)\bRFU\b|reasons?\s+for\s+update")
HIGHLIGHTS_TITLE_RE = re.compile(r"(?im)^\s*HIGHLIGHTS\s*$")


def highlights_rfu_dmc_pages(
    pages: Sequence[ParsedPage],
) -> dict[str, int] | None:
    """Return DMCs on HIGHLIGHTS pages carrying an RFU marker, or None if absent."""
    rfu_pages = [
        page
        for page in pages
        if HIGHLIGHTS_TITLE_RE.search(page.text) and RFU_RE.search(page.text)
    ]
    if not rfu_pages:
        return None
    return {
        dmc: page.page
        for page in rfu_pages
        for dmc in DMC_RE.findall(unwrap_dmc(page.text))
    }


def _run(
    context: Any,
    _parameters: Mapping[str, Any],
) -> tuple[OperationResult, list[OperationResult]]:
    expected = "DMC des HIGHLIGHTS avec reason for update : statut C ou R dans la LOEDM"
    runtime = getattr(context, "runtime", context)
    parsed = getattr(runtime, "parsed_pdf", None)
    if getattr(runtime, "is_docx", False) or not isinstance(parsed, ParsedPdf):
        return (
            OperationResult(
                status="INCONCLUSIVE",
                expected=expected,
                message="Contrôle disponible uniquement sur un PDF analysé.",
            ),
            [],
        )

    pages = complete_pages(parsed)
    highlights_pages = [
        page for page in pages if HIGHLIGHTS_TITLE_RE.search(page.text)
    ]
    if not highlights_pages:
        return (
            OperationResult(
                status="INCONCLUSIVE",
                expected=expected,
                message="Page HIGHLIGHTS introuvable ou illisible dans le PDF.",
            ),
            [],
        )

    rows, _loedm_pages = parse_loedm(pages)
    if not rows:
        return (
            OperationResult(
                status="INCONCLUSIVE",
                expected=expected,
                message="LIST OF EFFECTIVE DATA MODULES introuvable ou illisible dans le PDF.",
            ),
            [],
        )

    highlights = highlights_rfu_dmc_pages(pages)
    if highlights is None:
        return OperationResult(status="PASS", expected=expected), []
    if not highlights:
        return (
            OperationResult(
                status="INCONCLUSIVE",
                expected=expected,
                message="Reason for update détecté dans HIGHLIGHTS, mais aucun DMC lisible.",
            ),
            [],
        )

    rows_by_dmc: dict[str, list[Any]] = {}
    for row in rows:
        rows_by_dmc.setdefault(row.dmc, []).append(row)

    failures: list[OperationResult] = []
    for dmc, highlights_page in highlights.items():
        matching_rows = rows_by_dmc.get(dmc, [])
        if not matching_rows:
            failures.append(
                OperationResult(
                    status="FAIL",
                    expected=expected,
                    observed="DMC absent de la LOEDM",
                    message=f"DM {dmc} avec reason for update dans HIGHLIGHTS absent de la LOEDM.",
                    original=dmc,
                    proposed="Ajouter le DMC à la LOEDM avec le statut C ou R.",
                    page=highlights_page,
                )
            )
            continue
        if any(row.status in {STATUS_CHANGED, STATUS_REVISED} for row in matching_rows):
            continue

        row = matching_rows[0]
        status = row.status or "absent"
        failures.append(
            OperationResult(
                status="FAIL",
                expected=expected,
                observed=status,
                message=(
                    f"DM {dmc} avec reason for update dans HIGHLIGHTS : "
                    f"statut LOEDM {status}, C ou R attendu."
                ),
                original=status,
                proposed="C ou R",
                page=row.page,
            )
        )

    targets = getattr(context, "targets", ())
    target_pages = {target.raw_page for target in targets}
    if target_pages:
        failures = [finding for finding in failures if finding.page in target_pages]
    if failures:
        return failures[0], failures
    return (
        OperationResult(
            status="PASS",
            expected=expected,
            page=targets[-1].raw_page if targets else None,
        ),
        [],
    )


def _execute(context: Any, parameters: Mapping[str, Any]) -> OperationResult:
    result, _findings = _run(context, parameters)
    return result


def _suggestions(
    context: Any,
    parameters: Mapping[str, Any],
) -> list[OperationResult]:
    _result, findings = _run(context, parameters)
    return findings


S1000D_HIGHLIGHTS_STATUS = ClientOperation(
    name="s1000d_highlights_status",
    execute=_execute,
    suggestions=_suggestions,
)
