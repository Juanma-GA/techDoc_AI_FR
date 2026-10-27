"""THALES preparation operations that need the whole document, not one text region.

They compare the document with the *new* revision declared in the preparation
mapping: a FAIL means the page still has to be modified.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.checks.client_bundle import ClientOperation, OperationResult
from app.core.compiled_rule_runtime import document_metadata
from app.parsers.pdf_parser import ParsedPage

from . import revision_engine as revision

ROR_NEW_ROW = "ror_new_row"
LEP_MODIFIED_PAGES = "lep_modified_pages"
_ROR_PAGE_TYPE = "ROR"
_LEP_PAGE_TYPE = "LEP"


def _runtime(context: Any) -> Any:
    return getattr(context, "runtime", context)


def _control(parameters: Mapping[str, Any]) -> str:
    control = parameters.get("control")
    if control not in {ROR_NEW_ROW, LEP_MODIFIED_PAGES}:
        raise ValueError("preparation_check operation requires a known control")
    return str(control)


def _document_pages(context: Any) -> list[ParsedPage]:
    parsed = getattr(_runtime(context), "parsed_pdf", None)
    if parsed is None:
        return []
    return list(parsed.full_document_pages or parsed.pages)


def _target_pages(context: Any) -> set[int]:
    return {target.raw_page for target in getattr(context, "targets", ())}


def _mapped_revision_date(context: Any) -> revision.DocDate | None:
    metadata = document_metadata(getattr(_runtime(context), "document", None))
    return revision.parse_date(metadata.get("meta_revision_date"))


def _ror_new_row(context: Any) -> OperationResult:
    ror_pages = [page for page in _document_pages(context) if page.page_type == _ROR_PAGE_TYPE]
    if not ror_pages:
        return OperationResult(status="INCONCLUSIVE", message="Aucune page ROR identifiée.")
    last_page = ror_pages[-1]
    targets = _target_pages(context)
    if targets and last_page.page not in targets:
        return OperationResult(status="PASS", page=last_page.page)
    revision_date = _mapped_revision_date(context)
    if revision_date is None or revision_date.day is None:
        return OperationResult(
            status="INCONCLUSIVE",
            page=last_page.page,
            message=(
                "La date de révision du mapping de préparation doit être au format "
                "MMM JJ/AA pour calculer la ligne ROR."
            ),
        )
    expected_insertion = revision._expected_ror_insertion_date(revision_date)
    entries = [entry for page in ror_pages for entry in revision.extract_ror(page)]
    for entry in entries:
        insertion = entry.insertion_date
        if (
            entry.revision_date is not None
            and entry.revision_date.same_as(revision_date)
            and insertion is not None
            and insertion.day is None
            and (insertion.month, insertion.year)
            == (expected_insertion.month, expected_insertion.year)
        ):
            return OperationResult(status="PASS", page=last_page.page)
    number = document_metadata(getattr(_runtime(context), "document", None)).get(
        "meta_revision_number"
    )
    row = f"REVISION DATE {revision_date.text} / INSERTION DATE {expected_insertion.text}"
    last_entry = entries[-1] if entries else None
    return OperationResult(
        status="FAIL",
        observed=last_entry.revision_date_text if last_entry else None,
        expected=row,
        message=(
            f"Ajouter au Record of Revisions une ligne"
            f"{f' REV. No. {number}' if number else ''} : {row}."
        ),
        page=last_page.page,
        bbox=last_entry.bbox if last_entry else None,
    )


def _lep_findings(context: Any) -> tuple[list[OperationResult], list[int]]:
    pages = _document_pages(context)
    lep_pages = [page for page in pages if page.page_type == _LEP_PAGE_TYPE]
    revision_date = _mapped_revision_date(context)
    modified = [page for page in pages if page.is_modified is True]
    if not lep_pages or revision_date is None or not modified:
        return [], []
    state = revision.RevisionState()
    for page in lep_pages:
        state.lep.extend(revision.extract_lep(page)[0])
    expected_text = f"{revision_date.text} *"
    findings: list[OperationResult] = []
    unresolved: list[int] = []
    for page in modified:
        footer = revision.extract_footer(page)
        entry = (
            state.lep_entry_for_key(footer.page_key)
            if footer is not None and footer.page_key
            else None
        )
        if entry is None:
            unresolved.append(page.page)
            continue
        if entry.date is not None and revision_date.same_as(entry.date) and entry.starred:
            continue
        findings.append(
            OperationResult(
                status="FAIL",
                observed=entry.date_text,
                expected=expected_text,
                original=entry.date_text,
                proposed=expected_text,
                message=(
                    f"La page {entry.page_key} commentée doit apparaître dans la LEP "
                    f"sous la forme « {expected_text} » (actuellement « {entry.date_text} »)."
                ),
                page=entry.page,
                bbox=entry.bbox,
            )
        )
    return findings, unresolved


def _evaluate(context: Any, parameters: Mapping[str, Any]) -> OperationResult:
    control = _control(parameters)
    if getattr(_runtime(context), "is_docx", False) or getattr(
        _runtime(context), "parsed_pdf", None
    ) is None:
        return OperationResult(status="INCONCLUSIVE", expected=control)
    if control == ROR_NEW_ROW:
        return _ror_new_row(context)
    if _mapped_revision_date(context) is None:
        return OperationResult(
            status="INCONCLUSIVE",
            message="La date de révision du mapping de préparation est absente.",
        )
    findings, unresolved = _lep_findings(context)
    targets = _target_pages(context)
    on_page = [item for item in findings if not targets or item.page in targets]
    if on_page:
        return on_page[0]
    if unresolved:
        pages = ", ".join(str(number) for number in unresolved)
        return OperationResult(
            status="INCONCLUSIVE",
            message=f"Pages commentées introuvables dans la LEP : {pages}.",
        )
    return OperationResult(status="PASS", expected=control)


def _suggest(context: Any, parameters: Mapping[str, Any]) -> list[OperationResult]:
    if _control(parameters) != LEP_MODIFIED_PAGES:
        return []
    targets = _target_pages(context)
    return [
        item for item in _lep_findings(context)[0] if not targets or item.page in targets
    ]


PREPARATION_CHECK = ClientOperation(
    name="preparation_check",
    execute=_evaluate,
    suggestions=_suggest,
)
