"""S1000D operations registered through the generic client-operation contract.

Three operations group the controls that need document structure; each one is
selected by the `control` parameter of the rule check:

- `s1000d_dm_status`: LOEDM dates/statuses and revision bars per data module.
- `s1000d_front_matter`: revision identification, copyright, SB record, acronyms.
- `s1000d_content`: writing style, sections, tables and links.

A control never reports a failure without evidence: when the expected structure
(LOEDM, heading, link annotations...) is not found in the PDF it returns
INCONCLUSIVE with the reason.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.checks.client_bundle import ClientOperation, OperationResult
from app.core.compiled_rule_runtime import document_metadata
from app.parsers.pdf_parser import ParsedPage, ParsedPdf

from .data_modules import (
    STATUS_CHANGED,
    STATUS_REVISED,
    STATUS_STATUS,
    IssueDate,
    LoedmRow,
    PageText,
    complete_pages,
    dm_page_map,
    ipl_page_numbers,
    parse_issue_date,
    parse_loedm,
    revision_bars,
    same_issue_date,
    unwrap_dmc,
)
from .highlights import (
    RFU_RE as _RFU_RE,
)
from .highlights import (
    S1000D_HIGHLIGHTS_STATUS,
    highlights_rfu_dmc_pages,
)

_STRUCTURE_ATTR = "_s1000d_structure"
_NO_PDF = "Contrôle disponible uniquement sur un PDF analysé."
_NO_LOEDM = "LIST OF EFFECTIVE DATA MODULES introuvable ou illisible dans le PDF."
_NO_STATUS = "Colonne statut illisible dans la LIST OF EFFECTIVE DATA MODULES."
_NO_REVISION_DATE = "Date de révision absente ou illisible dans le mapping du document."

_FRONT_MATTER_PAGES = 3
_SECTION_END_PAGES = 3

_RECORD_OF_REVISIONS_RE = re.compile(
    r"(?im)^\s*(?:RECORD\s+OF\s+REVISIONS|REVISION\s+RECORD|CHANGE\s+RECORD)\s*$"
)
_REVISION_NUMBER_RE = re.compile(
    r"(?i)\brevision\s*(?:no\.?|number|n\u00b0)?\s*:?\s*(?P<number>\d{1,3})\b"
)
_ISSUE_DATE_LABEL_RE = re.compile(r"(?i)\bissue\s+date\s*:?\s*(?P<date>[^\n]{4,30})")
# Title block of the published CMP: "Issue No: 005" followed by the issue date on the next line.
_ISSUE_BLOCK_RE = re.compile(
    r"(?im)^[ \t]*Issue[ \t]+No\.?[ \t]*:?[ \t]*(?P<number>\d{1,3})[ \t]*\n[ \t]*(?P<date>[^\n]{4,30})$"
)
_COPYRIGHT_YEARS_RE = re.compile(
    r"(?i)\u00a9\s*(?P<start>\d{4})\s*-\s*(?P<end>\d{4})(?=\s+THALES\s+AVS\s+FRANCE)"
)
_SB_RECORD_TITLE_RE = re.compile(
    r"(?im)^\s*(?:\d+[.)]?\s+)?Service\s+Bulletin\s+Record\s*$"
)
_ABBREVIATIONS_TITLE_RE = re.compile(r"(?im)^\s*LIST\s+OF\s+ABBREVIATIONS\s*$")
_SB_ACRONYM_RE = re.compile(r"(?im)^\s*SB\b[\s\S]{0,80}?\bService\s+Bulletin\b")
_SIL_ACRONYM_RE = re.compile(
    r"(?im)^\s*SILs?\b[\s\S]{0,80}?\bService\s+Information\s+Letters?\b"
)

_SB_RECORD_TEMPLATE = (
    "The Service Bulletin (SB) record lists all SBs incorporated in the manual.",
    "The SB record has the five columns that follow:",
    "SB \u2013 Number and revision:",
    "This is the number of the SB and its revision number.",
    "If no SB has an effect on the manual content, the comment \u201cNone\u201d is given.",
    "SB \u2013 Title:",
    "This is the subject of the SB.",
    "Equipment part number modification state:",
    "This is the equipment part number modification state.",
    "Only the part number(s) or amendment introduced is (are) listed.",
    "If the SB data has no effect on the manual content, the comment \u201cNo effect\u201d is given.",
    "Service bulletin release date:",
    "This is the release date of the SB",
    "Inserted number:",
    "This is the version of the manual that the SB has been incorporated into.",
    "The Service Information Letters (SILs) which have an effect on the manual content "
    "are given at the end of the table.",
)
_SB_RECORD_TABLE_HEADER = (
    "Number and revision",
    "Title",
    "Equipment part number modification state",
    "SB release date",
    "Inserted number",
)
_BREAKDOWN_TITLE_RE = re.compile(
    r"(?im)^\s*(?:Table\s+\S+\s+)?(?:Composition\s+Table|Detailed\s+Breakdown)\b[^\n]*$"
)
_BREAKDOWN_HEADER = ("Nomenclature", "Part Number", "Amendment Status", "Equipment Designator", "ATA No")
_BREAKDOWN_AMENDMENT_LETTERS = ("a", "b", "c", "d", "e", "f")
_BREAKDOWN_WINDOW = 700

# The mainProcedure element prints as "Procedure" under a lettered heading, ahead of "Close up".
_MAIN_PROCEDURE_RE = re.compile(r"(?im)^\s*(?:Main\s+procedure|Procedure)\s*$")
_PROCEDURE_END_RE = re.compile(
    r"(?im)^\s*(?:Requirements\s+after\s+job\s+completion|Preliminary\s+requirements|Close[\s-]*up)\s*$"
)
_JOB_SETUP_RE = re.compile(r"(?im)^\s*Job\s+set[\s-]*up\s*$")
_JOB_SETUP_END_RE = re.compile(
    r"(?im)^\s*(?:Main\s+procedure|Procedure|Requirements\s+after\s+job\s+completion)\s*$"
)
_PARAGRAPH_MARKER_RE = re.compile(
    r"(?m)^[ \t]*(?:\(\d+\)|\d+[.)]|\([a-z]\)|[A-Z][.)])[ \t]+\S"
)
_PRELIMINARY_CONDITIONS_RE = re.compile(r"(?i)\bpreliminary\s+conditions?\b")
_TOOLING_TABLE_RE = re.compile(
    r"(?is)\b(?:tool(?:ing)?|support\s+equipment)\b[^\n]{0,80}\b(?:qty|quantity)\b"
    r"|\b(?:additional|complementary|complement)\s+(?:tooling|tool)\s+information\b"
    r"|\btools?\s+additional\s+information\b"
)
_DASH_BULLET_RE = re.compile(r"(?m)^[ \t]*[-\u2010-\u2015\u2212\u2022][ \t]+(?P<rest>\S[^\n]*)$")

_STORAGE_INTRO_RE = re.compile(
    r"(?i)During\s+storage\s+operations,\s+make\s+sure\s+that\s+the\s+environmental"
    r"\s+conditions\s+are\s+as\s+follows\s*:"
)
_STORAGE_TITLE_RE = re.compile(r"(?m)^\s*STORAGE\s*$")
_STORAGE_TEMPERATURE_REFERENCE_RE = re.compile(
    r"(?i)Temperature\s*:\s*Refer\s+to\s+SPM[\s\S]{0,260}?Assemblies\.?"
)
_TEMPERATURE_LABEL_RE = re.compile(r"(?i)\bTemperature\s*:")
_TEMPERATURE_MENTION_RE = re.compile(
    r"(?i)\btemperatures?\b|\bdeg\.?\s*[CF]\b|\u00b0\s*[CF]\b"
)
_STORAGE_TRANSPORT_DM = "F9111CMON-A-20-02-00-00A-812A-A"
_STORAGE_TRANSPORT_TITLE_RE = re.compile(r"(?i)Storage\s+and\s+Transportation\s+of\s+Assemblies")
_HUMIDITY_RE = re.compile(r"(?i)\bRelative\s+humidity\b")
_HUMIDITY_DM = "F9111CMON-A-20-02-00-00A-800A-A"
# Looser than DMC_RE on purpose: an outdated reference such as ...-02000-800A-C is not a valid DMC.
_STORAGE_DM_REF_RE = re.compile(r"\bF9111CMON-A-20-02-00-[A-Z0-9]+-800A-[A-Z0-9]\b")
_REFERENCE_WINDOW = 450
_MANUAL_REFERENCE = {
    "airbus": re.compile(r"(?i)\bSPM\b|Standard\s+Practices\s+Manual"),
    "boeing": re.compile(r"(?i)\bSOPM\b|Standard\s+Overhaul\s+Practices\s+Manual"),
}
_MANUAL_LABEL = {"airbus": "SPM (Standard Practices Manual)", "boeing": "SOPM (Standard Overhaul Practices Manual)"}
_TABTOP_RE = re.compile(
    r"(?i)\bFirst\s+verification\s*:?\s*tabtop\b"
    r"|\bshop\s+verification\s+will\s+be\s+done\s+at\s+the\s+first\s+repair\b"
)
_OTHER_VERIFICATION_RE = re.compile(
    r"(?i)\bFirst\s+verification\s*:\s*(?!tabtop\b)\w+[^\n]*"
    r"|\bShop\s+check\s+which\s+is\s+done\s+by\s+(?!tab(?:le)?[\s-]*top\b)\w+[^\n]*"
)
_SHOP_VERIFICATION_TITLE_RE = re.compile(r"(?im)^\s*(?:\d+\.\s*)?Shop\s+Verification\s*$")
_TABTOP_SENTENCE = "The shop verification will be done at the first repair of the equipment."
_LOCTITE_RE = re.compile(r"(?i)\bLoctite\s*(?:\u00ae\s*)?(?P<grade>221|222)\b")
_SCREW_SIZE_RE = re.compile(r"\bM(?P<size>\d{1,2}(?:[.,]\d)?)\b")
_LOCTITE_SCREW_LIMIT = 5.0

_PROCEDURE_HEADING_RE = re.compile(
    r"(?im)^\s*(?:Preliminary\s+requirements|Main\s+procedure|Job\s+set[\s-]*up|Support\s+equipment)\b"
)
_FIGURE_RE = re.compile(r"(?im)^\s*(?:(?:Figure|Fig\.|IPD\s+figure)\s+\S+|ICN-\S+)")

_NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
_LARGE_NUMBER_WORDS = {
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
}
_SMALL_NUMBER_RE = re.compile(
    r"(?<![\w./,:+-])(?P<prev>[A-Za-z]+)[ \t]+(?P<number>\d)[ \t]+(?P<next>[A-Za-z]+)\b(?![.,]?\d)"
)
_LARGE_NUMBER_WORD_RE = re.compile(
    r"\b(?P<word>" + "|".join(_LARGE_NUMBER_WORDS) + r")[ \t]+(?P<next>[a-z]+)\b"
)
# A digit stays a digit after a label or before a unit.
_NUMBER_CONTEXT_WORDS = frozenset(
    "figure fig step item table page section chapter revision rev issue note no number "
    "qty quantity ref refer index sheet view detail zone area tool ata dm version vol "
    "volume part pn level type class grade series model line row column key position pos "
    "para paragraph ch sb pe fee sil icn code group kit stage phase pin slot channel port "
    "terminal connector wire frame plate cavity circuit plug jack test size".split()
)
_UNIT_WORDS = frozenset(
    "mm cm m km in inch inches ft bar bars psi pa kpa mpa n nm v a ma w hz khz mhz deg "
    "degree degrees c f kg g lb lbs lbf oz h hr hrs hour hours min minute minutes s sec "
    "second seconds percent ohm ohms db rpm l ml litre liter gal day days month months "
    "year years".split()
)


@dataclass
class _Outcome:
    """What one control found; `inconclusive` is set when the structure is missing."""

    expected: str
    findings: list[OperationResult] = field(default_factory=list)
    inconclusive: str | None = None


@dataclass(frozen=True)
class _Document:
    parsed: ParsedPdf
    pages: list[ParsedPage]
    meta: dict[str, str]
    target_pages: set[int]


@dataclass(frozen=True)
class _Structure:
    rows: list[LoedmRow]
    loedm_pages: list[int]
    page_map: dict[int, str]


Control = Callable[[_Document, Mapping[str, Any]], _Outcome]


def _fail(
    page: int,
    original: str,
    message: str,
    *,
    proposed: str | None = None,
    expected: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    strategy: str | None = None,
) -> OperationResult:
    return OperationResult(
        status="FAIL",
        observed=original or message,
        expected=expected or proposed,
        message=message,
        original=original,
        proposed=proposed,
        page=page,
        bbox=bbox,
        bbox_strategy=strategy,  # type: ignore[arg-type]
    )


def _missing(page: int, message: str, *, proposed: str | None = None) -> OperationResult:
    """A finding without an anchor in the text: the suggestion is placed in the empty page middle."""
    return _fail(page, "", message, proposed=proposed, strategy="empty_middle")


def _inconclusive(expected: str, reason: str) -> _Outcome:
    return _Outcome(expected=expected, inconclusive=reason)


def _line_at(text: str, index: int) -> str:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    return text[start : end if end >= 0 else len(text)].strip()


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[^0-9a-z]+", " ", normalized).split())


_ACRONYM_FOLD_RE = re.compile(
    r"\b(?:service bulletins?|service information letters?|sbs?|sils?|s)\b"
)


def _fold_without_acronyms(value: str) -> str:
    """Fold, then drop the SB/SIL acronyms that the PDF prints as separate links, out of sentence order."""
    return " ".join(_ACRONYM_FOLD_RE.sub(" ", _fold(value)).split())


def _structure(doc: _Document) -> _Structure:
    cached = getattr(doc.parsed, _STRUCTURE_ATTR, None)
    if cached is None:
        rows, loedm_pages = parse_loedm(doc.pages)
        cached = _Structure(
            rows,
            loedm_pages,
            dm_page_map(doc.pages, rows, loedm_pages) if rows else {},
        )
        setattr(doc.parsed, _STRUCTURE_ATTR, cached)
    return cached


def _dm_pages(structure: _Structure) -> dict[str, list[int]]:
    pages: dict[str, list[int]] = {}
    for number, dmc in structure.page_map.items():
        pages.setdefault(dmc, []).append(number)
    return pages


def _revision_date(doc: _Document) -> tuple[IssueDate | None, str | None]:
    raw = doc.meta.get("meta_revision_date")
    return parse_issue_date(raw), raw


# --------------------------------------------------------------------------- dm_status


def _loedm_dates(scope: str) -> Control:
    def control(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
        structure = _structure(doc)
        expected = "Date d'émission de chaque DM = date de révision"
        if not structure.rows:
            return _inconclusive(expected, _NO_LOEDM)
        revision, raw = _revision_date(doc)
        if revision is None:
            return _inconclusive(expected, _NO_REVISION_DATE)
        if scope == "modified" and not any(row.status for row in structure.rows):
            return _inconclusive(expected, _NO_STATUS)
        # Generic DMs are shared between publications and keep their own issue date.
        rows = [
            row
            for row in structure.rows
            if (row.modified if scope == "modified" else not row.generic)
        ]
        readable = [row for row in rows if row.issue_date is not None]
        if rows and not readable:
            return _inconclusive(expected, "Dates des DM illisibles dans la LOEDM.")
        outcome = _Outcome(expected=f"{expected} ({raw})")
        for row in readable:
            if row.issue_date is not None and not same_issue_date(row.issue_date, revision):
                outcome.findings.append(
                    _fail(
                        row.page,
                        row.dmc,
                        f"DM {row.dmc} : date {row.issue_date_text} différente de la date "
                        f"de révision {raw}.",
                        proposed=raw,
                    )
                )
        return outcome

    return control


def _loedm_status_modified(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "Statut renseigné dans la LOEDM (C si le contenu est modifié) pour chaque DM modifié"
    structure = _structure(doc)
    if not structure.rows:
        return _inconclusive(expected, _NO_LOEDM)
    revision, _raw = _revision_date(doc)
    if revision is None:
        return _inconclusive(expected, _NO_REVISION_DATE)
    if not any(row.status for row in structure.rows):
        return _inconclusive(expected, _NO_STATUS)
    outcome = _Outcome(expected=expected)
    for row in structure.rows:
        if row.issue_date is None or not same_issue_date(row.issue_date, revision):
            continue
        if not row.modified:
            outcome.findings.append(
                _fail(
                    row.page,
                    row.dmc,
                    f"DM {row.dmc} modifié (date {row.issue_date_text}) : statut absent dans la "
                    "LOEDM (C attendu).",
                    proposed=STATUS_CHANGED,
                )
            )
    return outcome


def _loedm_status_all(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "Statut C pour tous les DM hors DM génériques"
    structure = _structure(doc)
    if not structure.rows:
        return _inconclusive(expected, _NO_LOEDM)
    if not any(row.status for row in structure.rows):
        return _inconclusive(expected, _NO_STATUS)
    outcome = _Outcome(expected=expected)
    for row in structure.rows:
        if row.generic or row.status == STATUS_CHANGED:
            continue
        outcome.findings.append(
            _fail(
                row.page,
                row.dmc,
                f"DM {row.dmc} : statut {row.status or 'absent'} au lieu de C.",
                proposed=STATUS_CHANGED,
            )
        )
    return outcome


def _bar_context(
    doc: _Document,
    expected: str,
) -> tuple[_Structure, dict[int, ParsedPage]] | _Outcome:
    structure = _structure(doc)
    if not structure.rows:
        return _inconclusive(expected, _NO_LOEDM)
    if not any(row.status for row in structure.rows):
        return _inconclusive(expected, _NO_STATUS)
    if not any(page.vector_primitives for page in doc.pages):
        return _inconclusive(
            expected, "Aucun élément vectoriel dans le PDF : barres de révision non détectables."
        )
    return structure, {page.page: page for page in doc.pages}


def _highlights_dmcs(doc: _Document) -> set[str] | None:
    """DMCs listed on the HIGHLIGHTS pages, where the reasons for update (RFU) are printed."""
    dmcs = highlights_rfu_dmc_pages(doc.pages)
    return None if dmcs is None else set(dmcs)


def _changed_dm_bars(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "Barres de révision et RFU pour chaque DM au statut C"
    context = _bar_context(doc, expected)
    if isinstance(context, _Outcome):
        return context
    structure, pages = context
    dm_pages = _dm_pages(structure)
    changed = [row for row in structure.rows if row.status == STATUS_CHANGED]
    highlights = _highlights_dmcs(doc)
    rfu_printed = highlights is not None or any(_RFU_RE.search(page.text) for page in doc.pages)
    outcome = _Outcome(expected=expected)
    mapped = 0
    for row in changed:
        numbers = dm_pages.get(row.dmc, [])
        if not numbers:
            continue
        mapped += 1
        if not any(revision_bars(pages[number]) for number in numbers):
            outcome.findings.append(
                _missing(
                    numbers[0],
                    f"DM {row.dmc} au statut C sans barre de révision.",
                    proposed="Barre de révision",
                )
            )
        if not rfu_printed:
            continue
        has_rfu = (
            row.dmc in highlights
            if highlights is not None
            else any(_RFU_RE.search(pages[number].text) for number in numbers)
        )
        if not has_rfu:
            where = "dans les HIGHLIGHTS" if highlights is not None else "dans le DM"
            outcome.findings.append(
                _missing(
                    numbers[0],
                    f"DM {row.dmc} au statut C sans RFU (reason for update) {where}.",
                    proposed="RFU",
                )
            )
    if changed and not mapped:
        return _inconclusive(expected, "Pages des DM introuvables (DMC absent des en-têtes/pieds).")
    return outcome


def _unchanged_dm_no_bars(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "Aucune barre de révision dans les DM aux statuts revised/status"
    context = _bar_context(doc, expected)
    if isinstance(context, _Outcome):
        return context
    structure, pages = context
    dm_pages = _dm_pages(structure)
    rows = [row for row in structure.rows if row.status in {STATUS_REVISED, STATUS_STATUS}]
    outcome = _Outcome(expected=expected)
    for row in rows:
        for number in dm_pages.get(row.dmc, []):
            bars = revision_bars(pages[number])
            if bars:
                bar = bars[0]
                outcome.findings.append(
                    _fail(
                        number,
                        "",
                        f"DM {row.dmc} au statut {row.status} : barre de révision à supprimer.",
                        bbox=(bar.x - 2.0, bar.top, bar.x + 2.0, bar.bottom),
                    )
                )
                break
    return outcome


def _ipl_changed(
    doc: _Document,
    expected: str,
) -> tuple[_Structure, dict[int, ParsedPage], list[int]] | _Outcome:
    context = _bar_context(doc, expected)
    if isinstance(context, _Outcome):
        return context
    structure, pages = context
    ipl_rows = [row for row in structure.rows if row.info_code.startswith("941")]
    if not ipl_rows:
        return _inconclusive(expected, "DM de l'IPL (code d'information 941) introuvable dans la LOEDM.")
    dm_pages = _dm_pages(structure)
    changed_pages = [
        number
        for row in ipl_rows
        if row.status == STATUS_CHANGED
        for number in dm_pages.get(row.dmc, [])
    ]
    return structure, pages, changed_pages


def _ipl_revision_bars(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "Barres de révision dans l'IPL lorsque le DM IPL est mis à jour (statut C)"
    context = _ipl_changed(doc, expected)
    if isinstance(context, _Outcome):
        return context
    _structure_value, pages, changed_pages = context
    outcome = _Outcome(expected=expected)
    if changed_pages and not any(revision_bars(pages[number]) for number in changed_pages):
        outcome.findings.append(
            _missing(
                changed_pages[0],
                "IPL mise à jour (statut C) sans barre de révision.",
                proposed="Barre de révision",
            )
        )
    return outcome


def _ipl_illustration_bars(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "Barre de révision sur les illustrations modifiées de l'IPL"
    context = _ipl_changed(doc, expected)
    if isinstance(context, _Outcome):
        return context
    _structure_value, pages, changed_pages = context
    figure_pages = [number for number in changed_pages if _FIGURE_RE.search(pages[number].text)]
    if figure_pages and not any(revision_bars(pages[number]) for number in figure_pages):
        return _inconclusive(
            expected,
            "DM IPL mis à jour : les marques de révision d'une illustration peuvent être "
            "intégrées à l'image, à vérifier visuellement.",
        )
    return _Outcome(expected=expected)


# ------------------------------------------------------------------------ front_matter


def _front_pages(doc: _Document) -> list[ParsedPage]:
    """Title block: first pages, up to the first page that opens a listing."""
    pages: list[ParsedPage] = []
    for page in doc.pages[:_FRONT_MATTER_PAGES]:
        if pages and (
            _RECORD_OF_REVISIONS_RE.search(page.text) or _ABBREVIATIONS_TITLE_RE.search(page.text)
        ):
            break
        pages.append(page)
    return pages


def _revision_number(value: str | None) -> int | None:
    digits = re.sub(r"\D", "", value or "")
    return int(digits) if digits else None


def _revision_identification(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "Numéro de révision et issue date = valeurs du mapping"
    number = _revision_number(doc.meta.get("meta_revision_number"))
    revision, raw_date = _revision_date(doc)
    if number is None or revision is None:
        return _inconclusive(expected, "Numéro ou date de révision absent du mapping du document.")
    outcome = _Outcome(expected=f"Révision {number:02d} — {raw_date}")
    seen = 0
    for page in _front_pages(doc):
        for match in _ISSUE_BLOCK_RE.finditer(page.text):
            seen += 1
            if int(match.group("number")) != number:
                outcome.findings.append(
                    _fail(
                        page.page,
                        match.group(0).splitlines()[0].strip(),
                        f"Numéro d'issue {match.group('number')} différent du mapping ({number:02d}).",
                        proposed=f"{number:03d}",
                    )
                )
            found = parse_issue_date(match.group("date"))
            if found is not None and not same_issue_date(found, revision):
                outcome.findings.append(
                    _fail(
                        page.page,
                        match.group("date").strip(),
                        f"Issue date {match.group('date').strip()} différente de la date de "
                        f"révision du mapping ({raw_date}).",
                        proposed=raw_date,
                    )
                )
        for match in _REVISION_NUMBER_RE.finditer(page.text):
            seen += 1
            if int(match.group("number")) != number:
                outcome.findings.append(
                    _fail(
                        page.page,
                        match.group(0).strip(),
                        f"Numéro de révision {match.group('number')} différent du mapping ({number:02d}).",
                        proposed=f"{number:02d}",
                    )
                )
        for match in _ISSUE_DATE_LABEL_RE.finditer(page.text):
            found = parse_issue_date(match.group("date"))
            if found is None:
                continue
            seen += 1
            if not same_issue_date(found, revision):
                outcome.findings.append(
                    _fail(
                        page.page,
                        match.group(0).strip(),
                        f"Issue date {match.group('date').strip()} différente de la date de "
                        f"révision du mapping ({raw_date}).",
                        proposed=raw_date,
                    )
                )
    if not seen:
        return _inconclusive(expected, "Numéro de révision / issue date introuvables en première page.")
    return outcome


def _revision_record_row(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "Ligne du Record of revisions (Change record) avec le numéro de révision et l'issue date"
    number = _revision_number(doc.meta.get("meta_revision_number"))
    revision, raw_date = _revision_date(doc)
    if number is None or revision is None:
        return _inconclusive(expected, "Numéro ou date de révision absent du mapping du document.")
    heading = next(
        (
            (index, page)
            for index, page in enumerate(doc.pages)
            if _RECORD_OF_REVISIONS_RE.search(page.text)
        ),
        None,
    )
    if heading is None:
        return _inconclusive(expected, "RECORD OF REVISIONS / CHANGE RECORD introuvable dans le PDF.")
    index, first = heading
    section = doc.pages[index : index + 2]
    for page in section:
        lines = page.text.splitlines()
        for position, line in enumerate(lines):
            if not re.search(rf"(?<!\d)0*{number}(?!\d)", line):
                continue
            window = " ".join(lines[position : position + 3])
            found = parse_issue_date(window)
            if found is not None and same_issue_date(found, revision):
                return _Outcome(expected=expected)
    title = _RECORD_OF_REVISIONS_RE.search(first.text)
    anchor = title.group(0).strip() if title is not None else ""
    outcome = _Outcome(expected=expected)
    outcome.findings.append(
        _fail(
            first.page,
            anchor,
            f"Aucune ligne pour la révision {number:02d} ({raw_date}) dans le Record of revisions.",
            proposed=f"{number:02d} {raw_date}",
        )
    )
    return outcome


def _copyright_years(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "Années du copyright = année de première issue et année de révision"
    revision, _raw = _revision_date(doc)
    first_issue_value = str(doc.meta.get("meta_first_issue_date") or "").strip()
    first_issue = parse_issue_date(first_issue_value)
    first_issue_year = (
        first_issue.year
        if first_issue is not None
        else int(first_issue_value)
        if re.fullmatch(r"\d{4}", first_issue_value)
        else None
    )
    if revision is None and first_issue_year is None:
        return _inconclusive(expected, "Dates de révision et de première issue absentes du mapping.")
    statements = [
        (page.page, match)
        for page in doc.pages
        for match in _COPYRIGHT_YEARS_RE.finditer(page.text)
    ]
    if not statements:
        return _inconclusive(expected, "Aucune mention de copyright THALES trouvée.")
    outcome = _Outcome(expected=expected)
    for number, match in statements:
        start, end = int(match.group("start")), int(match.group("end"))
        expected_start = first_issue_year if first_issue_year is not None else start
        expected_end = revision.year if revision is not None else end
        if start == expected_start and end == expected_end and start <= end:
            continue
        outcome.findings.append(
            _fail(
                number,
                match.group(0).strip(),
                f"Copyright {start}-{end} : années attendues {expected_start}-{expected_end}.",
                proposed=f"\u00a9 {expected_start}-{expected_end}",
            )
        )
    return outcome


def _sb_record_template(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "DM SB record conforme au modèle (texte d'introduction et en-têtes du tableau)"
    start = next(
        (
            index
            for index, page in enumerate(doc.pages)
            if _SB_RECORD_TITLE_RE.search(page.text)
        ),
        None,
    )
    if start is None:
        return _inconclusive(expected, "DM « Service bulletin record » introuvable dans le PDF.")
    section = doc.pages[start : start + _SECTION_END_PAGES]
    folded = f" {_fold_without_acronyms(' '.join(page.text for page in section))} "
    missing = [
        item
        for item in (*_SB_RECORD_TEMPLATE, *_SB_RECORD_TABLE_HEADER)
        if f" {_fold_without_acronyms(item)} " not in folded
    ]
    outcome = _Outcome(expected=expected)
    if missing:
        title = _SB_RECORD_TITLE_RE.search(section[0].text)
        quoted = " ; ".join(f"« {item} »" for item in missing[:4])
        extra = f" (+{len(missing) - 4})" if len(missing) > 4 else ""
        outcome.findings.append(
            _fail(
                section[0].page,
                title.group(0).strip() if title is not None else "",
                f"DM SB record non conforme au modèle, texte manquant : {quoted}{extra}.",
                proposed=missing[0],
            )
        )
    return outcome


def _abbreviation_acronyms(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "Acronymes SB et SIL dans la LIST OF ABBREVIATIONS"
    start = next(
        (
            index
            for index, page in enumerate(doc.pages)
            if _ABBREVIATIONS_TITLE_RE.search(page.text)
        ),
        None,
    )
    if start is None:
        return _inconclusive(expected, "LIST OF ABBREVIATIONS introuvable dans le PDF.")
    section = doc.pages[start : start + _SECTION_END_PAGES + 1]
    text = "\n".join(page.text for page in section)
    missing = [
        label
        for label, pattern in (
            ("SB — Service Bulletin", _SB_ACRONYM_RE),
            ("SIL — Service Information Letter", _SIL_ACRONYM_RE),
        )
        if pattern.search(text) is None
    ]
    outcome = _Outcome(expected=expected)
    if missing:
        title = _ABBREVIATIONS_TITLE_RE.search(section[0].text)
        outcome.findings.append(
            _fail(
                section[0].page,
                title.group(0).strip() if title is not None else "",
                "Acronyme(s) absent(s) de la LIST OF ABBREVIATIONS : " + ", ".join(missing) + ".",
                proposed=missing[0],
            )
        )
    return outcome


# ---------------------------------------------------------------------------- content


def _sections(
    doc: _Document,
    start: re.Pattern[str],
    end: re.Pattern[str],
) -> list[tuple[PageText, int, int]]:
    """Text spans between each `start` heading and the next `end` heading (or the document end)."""
    joined = PageText.build(doc.pages)
    spans: list[tuple[PageText, int, int]] = []
    for match in start.finditer(joined.text):
        following = end.search(joined.text, match.end())
        spans.append((joined, match.end(), following.start() if following else len(joined.text)))
    return spans


def _numbers_in_words(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    outcome = _Outcome(expected="Chiffres de 0 à 9 en lettres, nombres à partir de 10 en chiffres")
    for page in doc.pages:
        for match in _SMALL_NUMBER_RE.finditer(page.text):
            prev, nxt = match.group("prev").casefold(), match.group("next").casefold()
            if prev in _NUMBER_CONTEXT_WORDS or nxt in _UNIT_WORDS:
                continue
            word = _NUMBER_WORDS[int(match.group("number"))]
            original = match.group(0)
            outcome.findings.append(
                _fail(
                    page.page,
                    original,
                    f"Le chiffre {match.group('number')} doit s'écrire en lettres ({word}).",
                    proposed=original.replace(match.group("number"), word, 1),
                )
            )
        for match in _LARGE_NUMBER_WORD_RE.finditer(page.text):
            number = _LARGE_NUMBER_WORDS[match.group("word")]
            original = match.group(0)
            outcome.findings.append(
                _fail(
                    page.page,
                    original,
                    f"« {match.group('word')} » doit s'écrire en chiffres ({number}).",
                    proposed=original.replace(match.group("word"), number, 1),
                )
            )
    return outcome


def _procedure_list_markers(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    outcome = _Outcome(expected="Sous-étapes de la procédure en (a), (b)... sans tiret")
    for joined, start, end in _sections(doc, _MAIN_PROCEDURE_RE, _PROCEDURE_END_RE):
        letter = 0
        last_line = -10
        for match in _DASH_BULLET_RE.finditer(joined.text, start, end):
            line_number = joined.text.count("\n", 0, match.start())
            letter = letter + 1 if line_number - last_line <= 3 else 1
            last_line = line_number
            page, _local = joined.locate(match.start())
            marker = chr(ord("a") + (letter - 1) % 26)
            original = match.group(0).strip()
            outcome.findings.append(
                _fail(
                    page.page,
                    original,
                    "Tiret dans la procédure : utiliser un repère (a), (b)...",
                    proposed=f"({marker}) {match.group('rest')}",
                )
            )
    return outcome


def _job_setup_section(doc: _Document) -> list[tuple[ParsedPage, str]]:
    sections: list[tuple[ParsedPage, str]] = []
    for index, page in enumerate(doc.pages):
        heading = _JOB_SETUP_RE.search(page.text)
        if heading is None:
            continue
        window = doc.pages[index : index + _SECTION_END_PAGES]
        text = page.text[heading.end() :] + "\n" + "\n".join(item.text for item in window[1:])
        end = _JOB_SETUP_END_RE.search(text)
        sections.append((page, text[: end.start()] if end else text))
    return sections


def _job_setup_preliminary_conditions(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    outcome = _Outcome(expected="Sous-paragraphe « Preliminary conditions » dans le Job set up")
    for page, text in _job_setup_section(doc):
        if len(_PARAGRAPH_MARKER_RE.findall(text)) < 2:
            continue
        if _PRELIMINARY_CONDITIONS_RE.search(text):
            continue
        heading = _JOB_SETUP_RE.search(page.text)
        outcome.findings.append(
            _fail(
                page.page,
                heading.group(0).strip() if heading is not None else "",
                "Job set up à plusieurs paragraphes sans sous-paragraphe « Preliminary conditions ».",
                proposed="Preliminary conditions",
            )
        )
    return outcome


def _job_setup_tooling_table(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "Tableau de complément d'information outillage si différent du DM CIR"
    sections = _job_setup_section(doc)
    if not sections:
        return _Outcome(expected=expected)
    if any(_TOOLING_TABLE_RE.search(text) for _page, text in sections):
        return _Outcome(expected=expected)
    return _inconclusive(
        expected,
        "Comparaison avec le DM CIR impossible depuis le PDF : vérifier si un tableau de "
        "complément d'information outillage est nécessaire dans le Job set up.",
    )


def _breakdown_table(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = " | ".join(_BREAKDOWN_HEADER)
    outcome = _Outcome(expected=expected)
    for page in doc.pages:
        for title in _BREAKDOWN_TITLE_RE.finditer(page.text):
            window = _fold(page.text[title.end() : title.end() + _BREAKDOWN_WINDOW])
            cursor, missing = 0, []
            for label in _BREAKDOWN_HEADER:
                position = window.find(_fold(label), cursor)
                if position < 0:
                    missing.append(label)
                else:
                    cursor = position + len(_fold(label))
            tokens = set(window.split())
            if "Amendment Status" not in missing:
                missing.extend(
                    f"colonne {letter.upper()}"
                    for letter in _BREAKDOWN_AMENDMENT_LETTERS
                    if letter not in tokens
                )
            if not missing:
                continue
            outcome.findings.append(
                _fail(
                    page.page,
                    title.group(0).strip(),
                    "Tableau de composition non conforme au modèle, élément manquant : "
                    + ", ".join(missing)
                    + ".",
                    proposed=expected,
                )
            )
    return outcome


def _storage_other_temperature(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    outcome = _Outcome(expected="Aucune autre mention de température que le renvoi de la NOTE STORAGE")
    for page in doc.pages:
        intro = _STORAGE_INTRO_RE.search(page.text)
        if intro is None:
            continue
        masked = _STORAGE_TEMPERATURE_REFERENCE_RE.sub(lambda m: " " * len(m.group(0)), page.text)
        # The renderer splits the NOTE bullet from its links: the label alone is the reference.
        label = _TEMPERATURE_LABEL_RE.search(masked, intro.end())
        if label is not None:
            masked = masked[: label.start()] + " " * len(label.group(0)) + masked[label.end() :]
        for match in _TEMPERATURE_MENTION_RE.finditer(masked):
            outcome.findings.append(
                _fail(
                    page.page,
                    _line_at(page.text, match.start()),
                    "Mention de température à supprimer : la NOTE STORAGE renvoie au DM des conditions "
                    "de température.",
                    proposed="",
                )
            )
    return outcome


def _manufacturer(doc: _Document) -> str:
    return "boeing" if doc.meta.get("meta_manufacturer", "").strip().casefold() == "boeing" else "airbus"


def _humidity_reference(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    manufacturer = _manufacturer(doc)
    outcome = _Outcome(
        expected=f"Relative humidity : renvoi à {_MANUAL_LABEL[manufacturer]} et au DM {_HUMIDITY_DM}"
    )
    for page in doc.pages:
        text = unwrap_dmc(page.text)
        for match in _HUMIDITY_RE.finditer(text):
            window = text[match.end() : match.end() + _REFERENCE_WINDOW]
            reference = _STORAGE_DM_REF_RE.search(window)
            if reference is None:
                outcome.findings.append(
                    _fail(
                        page.page,
                        _line_at(text, match.start()),
                        f"Relative humidity : renvoi au DM {_HUMIDITY_DM} absent.",
                        proposed=_HUMIDITY_DM,
                    )
                )
            elif reference.group(0) != _HUMIDITY_DM:
                outcome.findings.append(
                    _fail(
                        page.page,
                        reference.group(0),
                        f"Relative humidity : renvoi {reference.group(0)} obsolète, "
                        f"{_HUMIDITY_DM} attendu.",
                        proposed=_HUMIDITY_DM,
                    )
                )
            if not _MANUAL_REFERENCE[manufacturer].search(window):
                outcome.findings.append(
                    _fail(
                        page.page,
                        _line_at(text, match.start()),
                        f"Relative humidity : renvoi à {_MANUAL_LABEL[manufacturer]} absent "
                        f"(constructeur {manufacturer.capitalize()}).",
                        proposed=_MANUAL_LABEL[manufacturer],
                    )
                )
    return outcome


def _storage_temperature_note(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    manufacturer = _manufacturer(doc)
    expected = (
        "NOTE STORAGE : Temperature renvoyant à "
        f"{_MANUAL_LABEL[manufacturer]} et au DM {_STORAGE_TRANSPORT_DM}"
    )
    notes = [(page, _STORAGE_INTRO_RE.search(page.text)) for page in doc.pages]
    notes = [(page, intro) for page, intro in notes if intro is not None]
    if not notes:
        storage = [page for page in doc.pages if _STORAGE_TITLE_RE.search(page.text)]
        if not storage:
            return _inconclusive(expected, "Section STORAGE introuvable dans le PDF.")
        outcome = _Outcome(expected=expected)
        outcome.findings.append(
            _missing(
                storage[-1].page,
                "NOTE de renvoi au DM des conditions de température absente du STORAGE.",
                proposed=f"During storage operations, make sure that the environmental conditions "
                f"are as follows: Temperature: Refer to {_MANUAL_LABEL[manufacturer]}, "
                f"Refer to {_STORAGE_TRANSPORT_DM} - Storage and Transportation of Assemblies.",
            )
        )
        return outcome
    outcome = _Outcome(expected=expected)
    for page, intro in notes:
        # The links of the NOTE are printed after its text, in no fixed order.
        window = unwrap_dmc(page.text[intro.start() :])
        checks = (
            ("Temperature:", _TEMPERATURE_LABEL_RE.search(window) is not None),
            (_MANUAL_LABEL[manufacturer], _MANUAL_REFERENCE[manufacturer].search(window) is not None),
            (_STORAGE_TRANSPORT_DM, _STORAGE_TRANSPORT_DM in window),
            (
                "Storage and Transportation of Assemblies",
                _STORAGE_TRANSPORT_TITLE_RE.search(window) is not None,
            ),
        )
        missing = [label for label, found in checks if not found]
        if missing:
            outcome.findings.append(
                _fail(
                    page.page,
                    _line_at(page.text, intro.start()),
                    "NOTE STORAGE non conforme, élément(s) manquant(s) : " + " ; ".join(missing) + ".",
                    proposed=missing[0],
                )
            )
    return outcome


def _first_verification(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "First verification : TABTOP"
    if any(_TABTOP_RE.search(page.text) for page in doc.pages):
        return _Outcome(expected=expected)
    outcome = _Outcome(expected=expected)
    for page in doc.pages:
        for match in _OTHER_VERIFICATION_RE.finditer(page.text):
            outcome.findings.append(
                _fail(
                    page.page,
                    match.group(0).strip(),
                    "First verification différente de TABTOP.",
                    proposed=_TABTOP_SENTENCE,
                )
            )
    if outcome.findings:
        return outcome
    heading = next(
        (page for page in doc.pages if _SHOP_VERIFICATION_TITLE_RE.search(page.text)), doc.pages[0]
    )
    outcome.findings.append(
        _missing(heading.page, "First verification TABTOP absente.", proposed=_TABTOP_SENTENCE)
    )
    return outcome


def _screw_sizes(window: str) -> list[float]:
    return [float(match.group("size").replace(",", ".")) for match in _SCREW_SIZE_RE.finditer(window)]


def _loctite_grade(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
    expected = "Loctite 221 pour vis < M5, Loctite 222 pour vis > M5"
    outcome = _Outcome(expected=expected)
    without_size = 0
    for page in doc.pages:
        lines = page.text.splitlines()
        for position, line in enumerate(lines):
            match = _LOCTITE_RE.search(line)
            if match is None:
                continue
            sizes = _screw_sizes(" ".join(lines[max(position - 1, 0) : position + 2]))
            if not sizes:
                without_size += 1
                continue
            small = [size for size in sizes if size < _LOCTITE_SCREW_LIMIT]
            large = [size for size in sizes if size > _LOCTITE_SCREW_LIMIT]
            grade = match.group("grade")
            if grade == "221" and large and not small:
                wrong, right = large[0], "222"
                relation = ">"
            elif grade == "222" and small and not large:
                wrong, right = small[0], "221"
                relation = "<"
            else:
                continue
            outcome.findings.append(
                _fail(
                    page.page,
                    line.strip(),
                    f"Loctite {grade} avec une vis M{wrong:g} (vis {relation} M5) : utiliser Loctite {right}.",
                    proposed=_LOCTITE_RE.sub(lambda m: m.group(0).replace(grade, right), line.strip(), 1),
                )
            )
    if not outcome.findings and without_size:
        return _inconclusive(
            expected,
            f"{without_size} mention(s) Loctite sans diamètre de vis dans le texte : "
            "la désignation des vis se trouve dans l'IPL, à vérifier.",
        )
    return outcome


def _broken_links(pages: list[ParsedPage], what: str) -> list[OperationResult]:
    findings: list[OperationResult] = []
    for page in pages:
        for link in page.links:
            if not link.broken:
                continue
            label = f" « {link.text} »" if link.text else ""
            findings.append(
                _fail(page.page, "", f"Lien {what}{label} sans destination valide.", bbox=link.bbox)
            )
    return findings


def _links_control(*, ipl: bool) -> Control:
    def control(doc: _Document, _parameters: Mapping[str, Any]) -> _Outcome:
        expected = (
            "Liens de l'IPL fonctionnels" if ipl else "Liens de la procédure vers les outils fonctionnels"
        )
        if not any(page.links for page in doc.pages):
            return _inconclusive(expected, "Aucune annotation de lien dans le PDF (liens non exportés ?).")
        structure = _structure(doc)
        ipl_numbers = set(ipl_page_numbers(doc.pages, structure.rows, structure.page_map))
        if ipl:
            if not ipl_numbers:
                return _inconclusive(expected, "Pages de l'IPL introuvables dans le PDF.")
            pages = [page for page in doc.pages if page.page in ipl_numbers]
            return _Outcome(expected=expected, findings=_broken_links(pages, "de l'IPL"))
        procedure_dms = {
            structure.page_map[page.page]
            for page in doc.pages
            if page.page in structure.page_map and _PROCEDURE_HEADING_RE.search(page.text)
        }
        pages = [
            page
            for page in doc.pages
            if page.page not in ipl_numbers
            and (
                structure.page_map.get(page.page) in procedure_dms
                or _PROCEDURE_HEADING_RE.search(page.text)
            )
        ]
        return _Outcome(expected=expected, findings=_broken_links(pages, "de la procédure"))

    return control


# -------------------------------------------------------------------------- dispatch

_DM_STATUS_CONTROLS: dict[str, Control] = {
    "loedm_dates_all": _loedm_dates("all"),
    "loedm_dates_modified": _loedm_dates("modified"),
    "loedm_status_modified": _loedm_status_modified,
    "loedm_status_all": _loedm_status_all,
    "changed_dm_revision_bars": _changed_dm_bars,
    "unchanged_dm_no_revision_bars": _unchanged_dm_no_bars,
    "ipl_revision_bars": _ipl_revision_bars,
    "ipl_illustration_revision_bars": _ipl_illustration_bars,
}
_FRONT_MATTER_CONTROLS: dict[str, Control] = {
    "revision_identification": _revision_identification,
    "revision_record_row": _revision_record_row,
    "copyright_years": _copyright_years,
    "sb_record_template": _sb_record_template,
    "abbreviation_acronyms": _abbreviation_acronyms,
}
_CONTENT_CONTROLS: dict[str, Control] = {
    "first_verification": _first_verification,
    "numbers_in_words": _numbers_in_words,
    "procedure_list_markers": _procedure_list_markers,
    "job_setup_preliminary_conditions": _job_setup_preliminary_conditions,
    "job_setup_tooling_table": _job_setup_tooling_table,
    "breakdown_table": _breakdown_table,
    "humidity_reference": _humidity_reference,
    "storage_temperature_note": _storage_temperature_note,
    "storage_other_temperature": _storage_other_temperature,
    "loctite_grade": _loctite_grade,
    "broken_links_procedure": _links_control(ipl=False),
    "broken_links_ipl": _links_control(ipl=True),
}


def _operation(name: str, controls: Mapping[str, Control]) -> ClientOperation[Any]:
    def run(context: Any, parameters: Mapping[str, Any]) -> _Outcome:
        control = parameters.get("control")
        handler = controls.get(control) if isinstance(control, str) else None
        if handler is None:
            raise ValueError(f"{name} operation requires a known control, got {control!r}")
        runtime = getattr(context, "runtime", context)
        parsed = getattr(runtime, "parsed_pdf", None)
        if getattr(runtime, "is_docx", False) or not isinstance(parsed, ParsedPdf):
            return _inconclusive(str(control), _NO_PDF)
        targets = getattr(context, "targets", ())
        doc = _Document(
            parsed=parsed,
            pages=complete_pages(parsed),
            meta=document_metadata(getattr(runtime, "document", None)),
            target_pages={target.raw_page for target in targets},
        )
        outcome = handler(doc, parameters)
        if doc.target_pages:
            outcome.findings = [
                finding for finding in outcome.findings if finding.page in doc.target_pages
            ]
        return outcome

    def execute(context: Any, parameters: Mapping[str, Any]) -> OperationResult:
        outcome = run(context, parameters)
        if outcome.findings:
            return outcome.findings[0]
        if outcome.inconclusive:
            return OperationResult(
                status="INCONCLUSIVE",
                expected=outcome.expected,
                message=outcome.inconclusive,
            )
        targets = getattr(context, "targets", ())
        return OperationResult(
            status="PASS",
            expected=outcome.expected,
            page=targets[-1].raw_page if targets else None,
        )

    def suggestions(context: Any, parameters: Mapping[str, Any]) -> list[OperationResult]:
        return run(context, parameters).findings

    return ClientOperation(name=name, execute=execute, suggestions=suggestions)


S1000D_DM_STATUS = _operation("s1000d_dm_status", _DM_STATUS_CONTROLS)
S1000D_FRONT_MATTER = _operation("s1000d_front_matter", _FRONT_MATTER_CONTROLS)
S1000D_CONTENT = _operation("s1000d_content", _CONTENT_CONTROLS)

OPERATIONS = {
    operation.name: operation
    for operation in (
        S1000D_DM_STATUS,
        S1000D_FRONT_MATTER,
        S1000D_CONTENT,
        S1000D_HIGHLIGHTS_STATUS,
    )
}
