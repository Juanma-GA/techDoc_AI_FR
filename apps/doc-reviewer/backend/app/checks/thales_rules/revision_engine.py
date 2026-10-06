"""Cross-source detection of the pages revised by a THALES revision.

Three sources describe the same fact — « which pages did this revision
touch » — and they must agree before any other control is worth running:
                f"d'étoile et sa date {lep_entry.date_text} correspond au pied de "
1. the **Highlights** table: one row per revised block, with a status
   letter (``R`` revised, ``N`` new, ``U`` unchanged, ``D`` deleted);
2. the **List of Effective Pages** (LEP): every effective page with its
   date, plus a ``*`` when the page is modified/inserted/deleted. Each
   physical line of that table carries TWO independent entries (the
   three columns SUBJECT/PAGE/DATE are repeated side by side);
3. the **footer** of the page itself, which carries the date the page
   was last issued.

The tables are rebuilt from span geometry rather than from
``page.get_text()``: the reading order PyMuPDF produces on a two-group
table interleaves the left and right halves, which makes a purely
textual parse unusable. Column boundaries are derived from the table
header row itself, so a document with a different page width or margin
still parses.

The resulting :class:`RevisionState` is the prerequisite of every other
control: it tells which parsed pages are modified (``page.is_modified``)
so content rules only fire where the reviewer is actually allowed to
edit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Literal

from app.parsers.pdf_parser import ParsedPage, ParsedPdf, PdfWord, Span


_ROW_TOLERANCE = 3.0
_COLUMN_TOLERANCE = 8.0
_SUBJECT_ANCHOR_TOLERANCE = 6.0
_FOOTER_BAND_MIN_HEIGHT = 80.0

_HIGHLIGHTS_STATUSES = frozenset({"N", "D", "R", "U"})
_MODIFIED_STATUSES = frozenset({"N", "R"})

_MONTHS = (
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
)
_MONTH_INDEX = {name: index for index, name in enumerate(_MONTHS, start=1)}
_DATE_RE = re.compile(
    rf"(?i)\b(?P<month>{'|'.join(_MONTHS)})\s+(?:(?P<day>\d{{1,2}})\s*/\s*)?(?P<year>\d{{4}}|\d{{2}})\b"
)
# Two-digit years in these manuals span 1966 -> today; anything below the
# pivot is a 2000s year (26 = 2026), anything above is a 1900s one (66 = 1966).
_YEAR_PIVOT = 50

_HIGHLIGHTS_HEADER_RE = re.compile(r"(?i)chapter\s*/\s*section")
_DESIGNATION_HEADER_RE = re.compile(r"(?i)^designation$")
_CHANGE_HEADER_RE = re.compile(r"(?i)^description\s+of\s+change$")
_LEP_TITLE_RE = re.compile(r"(?i)\blist\s+of\s+effective\s+pages\b")
_LEP_TITLE_LINE_RE = re.compile(r"(?im)^\s*list\s+of\s+effective\s+pages\s*$")
_HIGHLIGHTS_TITLE_RE = re.compile(r"(?im)^\s*highlights\s*$")
_ROR_TITLE_RE = re.compile(r"(?im)^\s*record\s+of\s+revisions\s*$")
_ROR_REVISION_DATE_HEADER_RE = re.compile(r"(?i)\brevision\s+date\b")
_ROR_INSERTION_DATE_HEADER_RE = re.compile(r"(?i)\binsertion\s+date\b")
_TITLE_PAGE_RE = re.compile(r"(?im)^\s*overhaul\s+manual\s*$")
_TITLE_PAGE_ANCHOR_RE = re.compile(
    r"(?im)^\s*(?:first\s+issue\s*:|part\s+number|important\s+notice)\b"
)
_LEP_HEADER_CELLS = ("SUBJECT", "PAGE", "DATE")

_COPYRIGHT_ANCHOR_RE = re.compile(r"(?i)THALES\s+AVS\s+FRANCE")
HIGHLIGHTS_KEY_PREFIX = "HIGHLIGHTS"
_PAGE_KEY_RE = re.compile(
    r"(?i)^(?:(?P<prefix>.+?)\s+)?(?P<number>\d+(?:-\d+)?)$"
)
_RANGE_SPLIT_RE = re.compile(
    r"(?i)\s+(?:to|thru|through)\s+|\s+[-–—]\s+|(?<=\d)[–—](?=\d)"
)
_BLANK_RE = re.compile(r"(?i)^blank\b")
_DELETED_LEP_RE = re.compile(r"(?i)^deleted\b")


@dataclass(frozen=True)
class DocDate:
    """A THALES issue date, comparable across its two written forms."""

    month: int
    day: int | None
    year: int
    text: str

    @property
    def sort_key(self) -> tuple[int, int, int]:
        return (self.year, self.month, self.day or 0)

    def same_as(self, other: "DocDate | None") -> bool:
        if other is None:
            return False
        return (self.month, self.day, self.year) == (other.month, other.day, other.year)


@dataclass(frozen=True)
class HighlightsEntry:
    subject: str
    pages_text: str
    page_keys: tuple[str, ...]
    status: str
    page: int
    bbox: tuple[float, float, float, float]
    status_bbox: tuple[float, float, float, float]
    page_number_x: float | None = None
    description: str = ""
    description_bbox: tuple[float, float, float, float] | None = None
    subject_description: str = ""
    subject_description_bbox: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class InvalidHighlightsDesignation:
    designation: str
    pages_text: str
    page_keys: tuple[str, ...]
    page: int
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class MissingHighlightsDesignation:
    pages_text: str
    page_keys: tuple[str, ...]
    page: int
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class LepEntry:
    subject: str
    page_key: str
    date: DocDate | None
    date_text: str
    is_blank: bool
    starred: bool
    page: int
    bbox: tuple[float, float, float, float]


def _lep_page_key_aliases(entry: LepEntry, page_key: str | None = None) -> set[str]:
    target_key = page_key or entry.page_key
    aliases = {target_key}
    subject_parts = entry.subject.split()
    for start in range(len(subject_parts)):
        subject_suffix = " ".join(subject_parts[start:])
        if not any(character.isalpha() for character in subject_suffix):
            continue
        alias = normalize_page_key(f"{subject_suffix} Page {target_key}")
        if alias is not None:
            aliases.add(alias)
    return aliases


@dataclass(frozen=True)
class RorEntry:
    revision_date: DocDate | None
    revision_date_text: str
    insertion_date: DocDate | None
    insertion_date_text: str
    page: int
    bbox: tuple[float, float, float, float] | None


@dataclass(frozen=True)
class PageFooter:
    page: int
    page_key: str | None
    observed_page_key: str | None
    label_text: str
    label_bbox: tuple[float, float, float, float] | None
    page_number_bbox: tuple[float, float, float, float] | None
    date: DocDate | None
    date_text: str
    date_bbox: tuple[float, float, float, float] | None


@dataclass
class RevisionState:
    """Everything the revision controls need, extracted once per run."""

    revision_date: DocDate | None = None
    first_issue_date: DocDate | None = None
    last_issue_date: DocDate | None = None
    full_document: bool = True
    highlights_pages: tuple[int, ...] = ()
    lep_pages: tuple[int, ...] = ()
    highlights: list[HighlightsEntry] = field(default_factory=list)
    invalid_highlights_designations: list[InvalidHighlightsDesignation] = field(
        default_factory=list
    )
    missing_highlights_designations: list[MissingHighlightsDesignation] = field(
        default_factory=list
    )
    lep: list[LepEntry] = field(default_factory=list)
    ror_entries: list[RorEntry] = field(default_factory=list)
    footers: list[PageFooter] = field(default_factory=list)
    expected_footer_keys: dict[int, str] = field(default_factory=dict)
    missing_footer_pages: tuple[int, ...] = ()
    findings: list["RevisionFinding"] = field(default_factory=list)

    @property
    def available(self) -> bool:
        """Whether the three sources were found and can be cross-checked."""
        return bool(self.highlights and self.lep and self.revision_date)

    @property
    def status_by_key(self) -> dict[str, str]:
        statuses: dict[str, str] = {}
        ambiguous: set[str] = set()
        for entry in self.highlights:
            for key in entry.page_keys:
                previous = statuses.get(key)
                if previous is not None and previous != entry.status:
                    ambiguous.add(key)
                else:
                    statuses[key] = entry.status
        for key in ambiguous:
            statuses.pop(key, None)
        return statuses

    @property
    def lep_by_key(self) -> dict[str, LepEntry]:
        entries: dict[str, LepEntry] = {}
        ambiguous: set[str] = set()
        for entry in self.lep:
            for key in _lep_page_key_aliases(entry):
                previous = entries.get(key)
                if previous is not None and previous is not entry:
                    ambiguous.add(key)
                else:
                    entries[key] = entry
        for key in ambiguous:
            entries.pop(key, None)
        return entries

    @property
    def footer_by_key(self) -> dict[str, PageFooter]:
        footers: dict[str, PageFooter] = {}
        ambiguous: set[str] = set()
        for footer in self.footers:
            page_key = self.expected_footer_keys.get(footer.page, footer.page_key)
            if page_key is not None:
                previous = footers.get(page_key)
                if previous is not None and previous is not footer:
                    ambiguous.add(page_key)
                else:
                    footers[page_key] = footer
        for key in ambiguous:
            footers.pop(key, None)
        return footers

    def lep_entry_for_key(self, page_key: str) -> LepEntry | None:
        matches = self.lep_entries_for_key(page_key)
        direct = [entry for entry in matches if entry.page_key == page_key]
        if len(direct) == 1:
            return direct[0]
        if direct:
            return None
        return matches[0] if len(matches) == 1 else None

    def lep_entries_for_key(self, page_key: str) -> list[LepEntry]:
        return [
            entry for entry in self.lep if page_key in _lep_page_key_aliases(entry)
        ]

    def highlights_status_for_lep(
        self,
        entry: LepEntry,
        page_key: str | None = None,
    ) -> str | None:
        aliases = _lep_page_key_aliases(entry, page_key)
        matches = [
            (len(key), status)
            for key, status in self.status_by_key.items()
            if key in aliases
        ]
        if not matches:
            return None
        best_length = max(length for length, _status in matches)
        statuses = {status for length, status in matches if length == best_length}
        return next(iter(statuses)) if len(statuses) == 1 else None

    def highlights_designation_rule_for(self, entry: LepEntry) -> str | None:
        aliases = _lep_page_key_aliases(entry)
        if any(
            page_key in aliases
            for issue in self.missing_highlights_designations
            for page_key in issue.page_keys
        ):
            return "CUSTOM_HIGHLIGHTS_DESIGNATION_REQUIRED"
        if any(
            page_key in aliases
            for issue in self.invalid_highlights_designations
            for page_key in issue.page_keys
        ):
            return "CUSTOM_REVISION_HIGHLIGHTS_STATUS"
        return None

    def is_declared_modified(self, page_key: str) -> bool:
        entry = self.lep_entry_for_key(page_key)
        status = (
            self.highlights_status_for_lep(entry)
            if entry is not None
            else self.status_by_key.get(page_key)
        )
        if status in _MODIFIED_STATUSES:
            return True
        return entry is not None and entry.starred

    def is_contested(self, page_key: str) -> bool:
        """Whether the star and the Highlights status disagree on this page.

        The star then has no trustworthy expected date behind it, so the
        footer control stays silent until the contradiction is resolved.
        """
        entry = self.lep_entry_for_key(page_key)
        if entry is None or not entry.starred:
            return False
        return self.highlights_status_for_lep(entry) not in _MODIFIED_STATUSES | {"D"}


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------


def _center_y(span: Span) -> float:
    return (span.bbox[1] + span.bbox[3]) / 2


def visual_rows(spans: list[Span]) -> list[list[Span]]:
    """Group spans into visual table rows, left to right, top to bottom."""
    groups: list[tuple[float, list[Span]]] = []
    for span in sorted(spans, key=lambda item: (_center_y(item), item.bbox[0])):
        if not span.text.strip():
            continue
        center = _center_y(span)
        if groups and abs(center - groups[-1][0]) <= _ROW_TOLERANCE:
            groups[-1][1].append(span)
        else:
            groups.append((center, [span]))
    return [sorted(row, key=lambda item: item.bbox[0]) for _center, row in groups]


def _merge_bbox(spans: list[Span]) -> tuple[float, float, float, float]:
    return (
        min(span.bbox[0] for span in spans),
        min(span.bbox[1] for span in spans),
        max(span.bbox[2] for span in spans),
        max(span.bbox[3] for span in spans),
    )


def _merge_bbox_values(
    first: tuple[float, float, float, float] | None,
    second: tuple[float, float, float, float] | None,
) -> tuple[float, float, float, float] | None:
    if first is None:
        return second
    if second is None:
        return first
    return (
        min(first[0], second[0]),
        min(first[1], second[1]),
        max(first[2], second[2]),
        max(first[3], second[3]),
    )


def _append_highlights_text(first: str, second: str) -> str:
    if not first:
        return second.strip()
    if not second:
        return first.strip()
    return f"{first.rstrip()} {second.lstrip()}".strip()


def _join_cell(spans: list[Span]) -> str:
    return " ".join(part for span in spans if (part := span.text.strip()))


def _join_raw_cell(spans: list[Span]) -> str:
    """Concatenate a cell without losing the spacing inside each span.

    The Highlights alignment control needs the exact characters, but a cell
    split over several spans has no space between them.
    """
    parts: list[str] = []
    for span in spans:
        if not span.text.strip():
            continue
        if parts and not parts[-1][-1].isspace() and not span.text[0].isspace():
            parts.append(" ")
        parts.append(span.text)
    return "".join(parts).strip()


def _words_in_bbox(
    page: ParsedPage,
    bbox: tuple[float, float, float, float],
) -> list[PdfWord]:
    if not page.words:
        return []
    row_center = (bbox[1] + bbox[3]) / 2
    row_tolerance = max((bbox[3] - bbox[1]) / 2, _ROW_TOLERANCE)
    return sorted(
        (
            word
            for word in page.words
            if abs((word.bbox[1] + word.bbox[3]) / 2 - row_center) <= row_tolerance
            and word.bbox[2] >= bbox[0] - _COLUMN_TOLERANCE
            and word.bbox[0] <= bbox[2] + _COLUMN_TOLERANCE
        ),
        key=lambda word: word.bbox[0],
    )


def _highlights_page_number_x(
    page: ParsedPage,
    bbox: tuple[float, float, float, float],
) -> float | None:
    words = _words_in_bbox(page, bbox)
    page_label_index = next(
        (
            index
            for index, word in enumerate(words)
            if word.text.strip().casefold() in {"page", "pages"}
        ),
        None,
    )
    if page_label_index is None:
        return None
    return next(
        (
            word.bbox[0]
            for word in words[page_label_index + 1 :]
            if re.fullmatch(r"\d+(?:-\d+)?", word.text.strip()) is not None
        ),
        None,
    )


def _join_subject(parts: list[str]) -> str:
    """Re-assemble a subject split over several rows, undoing hyphenation."""
    subject = ""
    for part in parts:
        if not subject:
            subject = part
        elif subject.endswith("-"):
            subject = subject[:-1] + part
        else:
            subject = f"{subject} {part}"
    return " ".join(subject.split())


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------


def parse_date(value: str | None) -> DocDate | None:
    """Read « JUL 27/26 », « JUL 66 » or « JUL 1966 » into a comparable date."""
    if not value:
        return None
    normalized = re.sub(
        rf"(?i)\b({'|'.join(_MONTHS)})_*\.(?=\s)",
        r"\1",
        value,
    )
    match = _DATE_RE.search(normalized)
    if match is None:
        return None
    year = int(match.group("year"))
    if year < 100:
        year += 2000 if year < _YEAR_PIVOT else 1900
    day = match.group("day")
    return DocDate(
        month=_MONTH_INDEX[match.group("month").upper()],
        day=int(day) if day is not None else None,
        year=year,
        text=" ".join(match.group(0).split()),
    )


# --------------------------------------------------------------------------
# Page keys
# --------------------------------------------------------------------------


def normalize_page_key(value: str) -> str | None:
    """Map every written form of a page id onto one comparable key.

    « ROR Page 1 », « ROR 1 » and « Page 401 » are the same page seen from
    the Highlights, the LEP and the footer respectively.
    """
    compact = " ".join(value.split()).strip()
    compact = re.sub(r"(?i)^pages?\s+(?=\d+(?:-\d+)?$)", "", compact)
    compact = re.sub(r"(?i)\s+pages?\s+(?=\d+(?:-\d+)?$)", " ", compact)
    if parse_date(compact) is not None:
        return None
    match = _PAGE_KEY_RE.fullmatch(compact)
    if match is None:
        return None
    prefix = match.group("prefix")
    number = match.group("number")
    return f"{' '.join(prefix.upper().split())} {number}" if prefix else number


def expand_page_range(value: str) -> tuple[str, ...]:
    """Expand « Pages 701 to 704 » / « TP 1 to TP 2 » into page keys."""
    compact = " ".join(value.split())
    parts = [part for part in _RANGE_SPLIT_RE.split(compact) if part and part.strip()]
    if not parts:
        return ()
    if len(parts) == 1:
        key = normalize_page_key(parts[0])
        return (key,) if key else ()
    start_key = normalize_page_key(parts[0])
    end_key = normalize_page_key(parts[-1])
    if start_key is None or end_key is None:
        return tuple(key for key in (start_key, end_key) if key)
    start_prefix, _, start_number = start_key.rpartition(" ")
    end_prefix, _, end_number = end_key.rpartition(" ")
    if not end_prefix:
        end_prefix = start_prefix
    elif start_prefix and start_prefix.startswith(f"{end_prefix} "):
        end_prefix = start_prefix
    if start_prefix != end_prefix:
        return (start_key, end_key)

    start_parts = re.fullmatch(r"(?P<major>\d+)(?:-(?P<minor>\d+))?", start_number)
    end_parts = re.fullmatch(r"(?P<major>\d+)(?:-(?P<minor>\d+))?", end_number)
    if start_parts is None or end_parts is None:
        return (start_key, end_key)
    if start_parts.group("minor") is None and end_parts.group("minor") is None:
        first, last = int(start_parts.group("major")), int(end_parts.group("major"))
        if last < first or last - first > 500:
            return (start_key, end_key)
        numbers = [str(number) for number in range(first, last + 1)]
    elif (
        start_parts.group("minor") is not None
        and end_parts.group("minor") is not None
        and start_parts.group("major") == end_parts.group("major")
    ):
        first, last = int(start_parts.group("minor")), int(end_parts.group("minor"))
        if last < first or last - first > 500:
            return (start_key, end_key)
        major = start_parts.group("major")
        numbers = [f"{major}-{number}" for number in range(first, last + 1)]
    else:
        return (start_key, end_key)
    return tuple(f"{start_prefix} {number}" if start_prefix else number for number in numbers)


def page_number_of(page_key: str) -> int | None:
    _prefix, _, number = page_key.rpartition(" ")
    return int(number) if number.isdigit() else None


def page_key_prefix(page_key: str | None) -> str:
    if not page_key:
        return ""
    prefix, _, _number = page_key.rpartition(" ")
    return prefix


# --------------------------------------------------------------------------
# Highlights table
# --------------------------------------------------------------------------


def _highlights_header(rows: list[list[Span]]) -> tuple[int, float, float, float] | None:
    """Locate the Highlights header row and its two column boundaries."""
    for index, row in enumerate(rows):
        designation = next(
            (span for span in row if _DESIGNATION_HEADER_RE.match(span.text.strip())),
            None,
        )
        change = next(
            (span for span in row if _CHANGE_HEADER_RE.match(span.text.strip())),
            None,
        )
        pages = next(
            (span for span in row if _HIGHLIGHTS_HEADER_RE.search(span.text)),
            None,
        )
        if designation is None or change is None or pages is None:
            continue
        # Column starts, not column ends: the data cells of this table are
        # left-aligned well before the (centered) header labels, so a
        # boundary taken on the header's right edge misclassifies them.
        pages_max = (pages.bbox[0] + designation.bbox[0]) / 2
        status_max = (designation.bbox[0] + change.bbox[0]) / 2
        return index, pages_max, status_max, designation.bbox[0]
    return None


def extract_highlights(page: ParsedPage) -> list[HighlightsEntry]:
    """Read one Highlights page into (subject, page range, status) entries."""
    rows = visual_rows(page.spans)
    header = _highlights_header(rows)
    if header is None:
        return []
    header_index, pages_max, status_max, designation_x = header

    entries: list[HighlightsEntry] = []
    subject = ""
    pending: list[str] = []
    subject_description = ""
    subject_description_bbox: tuple[float, float, float, float] | None = None
    previous_was_subject = False
    page_width = max((span.bbox[2] for span in page.spans), default=status_max + 100.0)
    for row in rows[header_index + 1 :]:
        designation_cells = [
            span
            for span in row
            if designation_x - _COLUMN_TOLERANCE <= span.bbox[0] < status_max
        ]
        status_cells = [
            span
            for span in designation_cells
            if span.text.strip().upper() in _HIGHLIGHTS_STATUSES
        ]
        designation_ids = {id(span) for span in designation_cells}
        pages_cells = [
            span
            for span in row
            if span.bbox[0] < status_max and id(span) not in designation_ids
        ]
        description_cells = [span for span in row if span.bbox[0] >= status_max]
        description_text = _join_raw_cell(description_cells)
        if not pages_cells:
            if description_cells and previous_was_subject:
                subject_description = _append_highlights_text(
                    subject_description, description_text
                )
                subject_description_bbox = _merge_bbox_values(
                    subject_description_bbox, _merge_bbox(description_cells)
                )
            elif description_cells and entries:
                previous = entries[-1]
                entries[-1] = replace(
                    previous,
                    description=_append_highlights_text(
                        previous.description, description_text
                    ),
                    description_bbox=_merge_bbox_values(
                        previous.description_bbox, _merge_bbox(description_cells)
                    ),
                )
            else:
                previous_was_subject = False
            continue
        if not status_cells:
            if designation_cells:
                previous_was_subject = False
                continue
            if not previous_was_subject:
                pending = []
                subject_description = ""
                subject_description_bbox = None
            pending.append(_join_cell(pages_cells))
            subject = _join_subject(pending)
            if description_cells:
                subject_description = _append_highlights_text(
                    subject_description, description_text
                )
                subject_description_bbox = _merge_bbox_values(
                    subject_description_bbox, _merge_bbox(description_cells)
                )
            else:
                row_bbox = _merge_bbox(pages_cells)
                subject_description_bbox = _merge_bbox_values(
                    subject_description_bbox,
                    (status_max, row_bbox[1], page_width, row_bbox[3]),
                )
            previous_was_subject = True
            continue
        previous_was_subject = False
        pages_text = _join_raw_cell(pages_cells)
        pages_bbox = _merge_bbox(pages_cells)
        row_bbox = _merge_bbox([*pages_cells, *status_cells])
        description_bbox = (
            _merge_bbox(description_cells)
            if description_cells
            else (status_max, row_bbox[1], page_width, row_bbox[3])
        )
        entries.append(
            HighlightsEntry(
                subject=subject,
                pages_text=pages_text,
                page_keys=expand_page_range(pages_text),
                status=status_cells[0].text.strip().upper(),
                page=page.page,
                bbox=pages_bbox,
                status_bbox=status_cells[0].bbox,
                page_number_x=_highlights_page_number_x(page, pages_bbox),
                description=description_text,
                description_bbox=description_bbox,
                subject_description=subject_description,
                subject_description_bbox=subject_description_bbox,
            )
        )
    return entries


def extract_invalid_highlights_designations(
    page: ParsedPage,
) -> list[InvalidHighlightsDesignation]:
    rows = visual_rows(page.spans)
    header = _highlights_header(rows)
    if header is None:
        return []
    header_index, _pages_max, status_max, designation_x = header

    invalid: list[InvalidHighlightsDesignation] = []
    for row in rows[header_index + 1 :]:
        page_cells = [
            span
            for span in row
            if span.bbox[0] < designation_x - _COLUMN_TOLERANCE
        ]
        designation_cells = [
            span
            for span in row
            if designation_x - _COLUMN_TOLERANCE <= span.bbox[0] < status_max
        ]
        if not page_cells or not designation_cells:
            continue
        pages_text = _join_raw_cell(page_cells)
        page_keys = expand_page_range(pages_text)
        if not page_keys:
            continue
        designation = _join_raw_cell(designation_cells)
        normalized = re.sub(r"\s+", "", designation).upper()
        if not normalized or normalized in _HIGHLIGHTS_STATUSES:
            continue
        invalid.append(
            InvalidHighlightsDesignation(
                designation=designation,
                pages_text=pages_text,
                page_keys=page_keys,
                page=page.page,
                bbox=_merge_bbox(designation_cells),
            )
        )
    return invalid


def extract_missing_highlights_designations(
    page: ParsedPage,
) -> list[MissingHighlightsDesignation]:
    rows = visual_rows(page.spans)
    header = _highlights_header(rows)
    if header is None:
        return []
    header_index, _pages_max, status_max, designation_x = header

    missing: list[MissingHighlightsDesignation] = []
    for row in rows[header_index + 1 :]:
        page_cells = [
            span
            for span in row
            if span.bbox[0] < designation_x - _COLUMN_TOLERANCE
        ]
        designation_cells = [
            span
            for span in row
            if designation_x - _COLUMN_TOLERANCE <= span.bbox[0] < status_max
        ]
        if not page_cells or any(span.text.strip() for span in designation_cells):
            continue
        pages_text = _join_raw_cell(page_cells)
        page_keys = expand_page_range(pages_text)
        if not page_keys:
            continue
        pages_bbox = _merge_bbox(page_cells)
        missing.append(
            MissingHighlightsDesignation(
                pages_text=pages_text,
                page_keys=page_keys,
                page=page.page,
                bbox=(
                    designation_x - _COLUMN_TOLERANCE,
                    pages_bbox[1],
                    status_max,
                    pages_bbox[3],
                ),
            )
        )
    return missing


# --------------------------------------------------------------------------
# List of Effective Pages
# --------------------------------------------------------------------------


def _lep_header(rows: list[list[Span]]) -> tuple[int, tuple[float, ...]] | None:
    """Locate the repeated SUBJECT/PAGE/DATE header and its column starts.

    The triplet is printed side by side as many times as the page has
    column groups — two on this layout, but the count is read off the
    header rather than assumed.
    """
    for index, row in enumerate(rows):
        cells = [
            span
            for span in row
            if span.text.strip().upper().rstrip(":") in _LEP_HEADER_CELLS
        ]
        labels = tuple(span.text.strip().upper().rstrip(":") for span in cells)
        groups, remainder = divmod(len(labels), len(_LEP_HEADER_CELLS))
        if not groups or remainder or labels != _LEP_HEADER_CELLS * groups:
            continue
        return index, tuple(span.bbox[0] for span in cells)
    return None


def _lep_group_entries(
    rows: list[list[Span]],
    page: ParsedPage,
    subject_x: float,
    page_x: float,
    date_x: float,
    right_bound: float,
    subject: str,
) -> tuple[list[LepEntry], str]:
    subject_max = (subject_x + page_x) / 2
    page_max = (page_x + date_x) / 2

    entries: list[LepEntry] = []
    pending: list[str] = []
    subject_continues = False
    for row in rows:
        cells = [span for span in row if subject_x - _COLUMN_TOLERANCE <= span.bbox[0] < right_bound]
        # Rows that only exist in another column group must not break the
        # contiguity of a subject spread over two consecutive lines.
        if not cells:
            continue
        subject_cells = [
            span
            for span in cells
            if span.bbox[0] < subject_max
            and abs(span.bbox[0] - subject_x) <= _SUBJECT_ANCHOR_TOLERANCE
        ]
        # Indented cells between the subject and the page column carry the
        # section prefix of the page id (« TP » in « TP 1 »).
        subject_ids = {id(span) for span in subject_cells}
        prefix_cells = [
            span
            for span in cells
            if span.bbox[0] < subject_max and id(span) not in subject_ids
        ]
        page_cells = [span for span in cells if subject_max <= span.bbox[0] < page_max]
        date_cells = [span for span in cells if span.bbox[0] >= page_max]

        fused_page_key = None
        subject_text = _join_cell(subject_cells)
        if (
            subject_cells
            and not page_cells
            and date_cells
            and any(
                span.bbox[2] >= page_x - _COLUMN_TOLERANCE
                for span in subject_cells
            )
        ):
            fused_page = re.fullmatch(
                r"(?P<subject>.+?)\s+(?P<page>\d+(?:-\d+)*)",
                subject_text,
            )
            if fused_page is not None:
                fused_page_key = normalize_page_key(fused_page.group("page"))
                if fused_page_key is not None:
                    subject_text = fused_page.group("subject").rstrip()

        if subject_cells:
            if not subject_continues:
                pending = []
            pending.append(subject_text)
            subject_continues = True
        else:
            subject_continues = False
        if pending:
            subject = _join_subject(pending)

        if not date_cells or (not page_cells and fused_page_key is None):
            continue
        # A subject line sharing its row with an entry only wraps onto the
        # next row when it reads unfinished; otherwise the next subject line
        # starts a new section (« Cleaning » then « Inspection »).
        if subject_continues and fused_page_key is None:
            subject_continues = pending[-1].rstrip().endswith(("-", ","))

        page_key = fused_page_key or normalize_page_key(
            " ".join(part for part in (_join_cell(prefix_cells), _join_cell(page_cells)) if part)
        )
        if page_key is None:
            continue
        date_text = _join_cell(date_cells)
        entries.append(
            LepEntry(
                subject=subject,
                page_key=page_key,
                date=parse_date(date_text),
                date_text=date_text,
                is_blank=bool(_BLANK_RE.match(date_text)),
                starred="*" in date_text,
                page=page.page,
                bbox=_merge_bbox(date_cells),
            )
        )
    return entries, subject


def extract_lep(page: ParsedPage, subject: str = "") -> tuple[list[LepEntry], str]:
    """Read one LEP page, returning its entries and the trailing subject.

    The subject is carried over because a section routinely spills from
    the last column group of a page into the first one of the next page.
    """
    rows = visual_rows(page.spans)
    header = _lep_header(rows)
    if header is None:
        return [], subject
    header_index, anchors = header
    body = rows[header_index + 1 :]
    page_width = max((span.bbox[2] for span in page.spans), default=anchors[-1] + 100.0)

    entries: list[LepEntry] = []
    for group in range(len(anchors) // len(_LEP_HEADER_CELLS)):
        subject_x, page_x, date_x = anchors[group * 3 : group * 3 + 3]
        next_group = (group + 1) * 3
        right_bound = (
            anchors[next_group] - _COLUMN_TOLERANCE
            if next_group < len(anchors)
            else page_width + 1.0
        )
        group_entries, subject = _lep_group_entries(
            body, page, subject_x, page_x, date_x, right_bound, subject
        )
        entries.extend(group_entries)
    return entries, subject


# --------------------------------------------------------------------------
# Record of revisions
# --------------------------------------------------------------------------


def _ror_header_index(rows: list[list[Span]]) -> int | None:
    revision_rows: list[int] = []
    insertion_rows: list[int] = []
    for index, row in enumerate(rows):
        row_text = _join_cell(row)
        if _ROR_REVISION_DATE_HEADER_RE.search(row_text):
            revision_rows.append(index)
        if _ROR_INSERTION_DATE_HEADER_RE.search(row_text):
            insertion_rows.append(index)
        if revision_rows and insertion_rows and revision_rows[-1] == insertion_rows[-1]:
            return revision_rows[-1]
    if not revision_rows or not insertion_rows:
        return None
    if abs(revision_rows[0] - insertion_rows[0]) <= 3:
        return max(revision_rows[0], insertion_rows[0])
    return None


def _ror_entries_from_value(
    page_number: int,
    value: str,
    bbox: tuple[float, float, float, float] | None,
    *,
    allow_missing_insertion: bool,
) -> list[RorEntry]:
    dates = [
        (parse_date(match.group(0)), " ".join(match.group(0).split()))
        for match in _DATE_RE.finditer(value)
    ]
    entries: list[RorEntry] = []
    for index, (revision_date, revision_text) in enumerate(dates):
        if revision_date is None or revision_date.day is None:
            continue
        insertion = next(
            (
                (date, date_text)
                for date, date_text in dates[index + 1 :]
                if date is not None and date.day is None
            ),
            None,
        )
        if insertion is None and not allow_missing_insertion:
            continue
        insertion_date, insertion_text = insertion or (None, "")
        entries.append(
            RorEntry(
                revision_date=revision_date,
                revision_date_text=revision_text,
                insertion_date=insertion_date,
                insertion_date_text=insertion_text,
                page=page_number,
                bbox=bbox,
            )
        )
    return entries


def extract_ror(page: ParsedPage) -> list[RorEntry]:
    """Read revision/insertion date pairs from a Record of Revisions page."""
    if not _is_ror_page(page):
        return []

    entries: list[RorEntry] = []
    if page.spans:
        rows = visual_rows(page.spans)
        header_index = _ror_header_index(rows)
        title_index = next(
            (
                index
                for index, row in enumerate(rows)
                if _ROR_TITLE_RE.search(_join_cell(row))
            ),
            -1,
        )
        start_index = max(header_index if header_index is not None else -1, title_index) + 1
        allow_missing = header_index is not None
        for row in rows[start_index:]:
            row_text = _join_cell(row)
            if _COPYRIGHT_ANCHOR_RE.search(row_text):
                break
            entries.extend(
                _ror_entries_from_value(
                    page.page,
                    row_text,
                    _merge_bbox(row),
                    allow_missing_insertion=allow_missing,
                )
            )
        return entries

    lines = (page.text or "").splitlines()
    header_lines = [
        index
        for index, line in enumerate(lines)
        if _ROR_REVISION_DATE_HEADER_RE.search(line)
        or _ROR_INSERTION_DATE_HEADER_RE.search(line)
    ]
    title_index = next(
        (index for index, line in enumerate(lines) if _ROR_TITLE_RE.search(line)),
        -1,
    )
    start_index = max(header_lines + [title_index]) + 1
    allow_missing = bool(header_lines)
    for line in lines[start_index:]:
        if _COPYRIGHT_ANCHOR_RE.search(line):
            break
        entries.extend(
            _ror_entries_from_value(
                page.page,
                line,
                None,
                allow_missing_insertion=allow_missing,
            )
        )
    return entries


# --------------------------------------------------------------------------
# Footers
# --------------------------------------------------------------------------


def _footer_spans(page: ParsedPage) -> list[Span]:
    if not page.spans:
        return []
    min_y = min(span.bbox[1] for span in page.spans)
    max_y = max(span.bbox[3] for span in page.spans)
    band_top = max_y - max((max_y - min_y) * 0.25, _FOOTER_BAND_MIN_HEIGHT)
    return [span for span in page.spans if span.bbox[3] >= band_top]


def _footer_block(page: ParsedPage) -> list[Span]:
    """Narrow the footer band down to the identification block.

    A LEP page carries table rows inside the 25% band used elsewhere, and
    those rows are made of bare page numbers and dates — exactly what a
    footer looks like. The mandatory THALES copyright paragraph anchors
    the real block.
    """
    spans = _footer_spans(page)
    if not spans:
        return []
    anchors = [span for span in spans if _COPYRIGHT_ANCHOR_RE.search(span.text)]
    if anchors:
        # Compare row centers, not tops: the page label is printed in a
        # larger font than the copyright line it shares its row with.
        top = min(_center_y(span) for span in anchors) - 2 * _ROW_TOLERANCE
    else:
        top = max(_center_y(span) for span in spans) - 25.0
    return [span for span in spans if _center_y(span) >= top]


def _page_number_bbox(
    date_span: Span | None,
) -> tuple[float, float, float, float] | None:
    if date_span is None:
        return None
    left, top, right, _bottom = date_span.bbox
    height = max(date_span.bbox[3] - date_span.bbox[1], 1.0)
    gap = max(height * 0.1, 0.5)
    return (
        left,
        max(0.0, top - gap - height),
        right,
        max(0.0, top - gap),
    )


def extract_footer(page: ParsedPage, fallback_key: str | None = None) -> PageFooter | None:
    """Read the page id and the issue date printed in the page footer.

    `fallback_key` names the page when the footer label is missing or
    unreadable — a section spread over several pages is still that many
    pages even if one of them forgot to print its number.
    """
    spans = _footer_block(page)
    if not spans:
        if fallback_key is None:
            return None
        return PageFooter(
            page=page.page,
            page_key=fallback_key,
            observed_page_key=None,
            label_text="",
            label_bbox=None,
            page_number_bbox=None,
            date=None,
            date_text="",
            date_bbox=None,
        )
    page_width = max(span.bbox[2] for span in page.spans)
    label_row: list[Span] | None = None
    label_text = ""
    observed_page_key: str | None = None
    for row in visual_rows(spans):
        label_parts = [
            span
            for span in row
            if parse_date(span.text) is None
            and not _COPYRIGHT_ANCHOR_RE.search(span.text)
        ]
        if not label_parts:
            continue
        label_bbox = _merge_bbox(label_parts)
        label_words = _words_in_bbox(page, label_bbox)
        candidate_text = (
            " ".join(word.text.strip() for word in label_words)
            if label_words
            else _join_cell(label_parts)
        )
        candidate = normalize_page_key(candidate_text)
        if candidate is None and _MULTIPLE_PAGE_NUMBERS_RE.fullmatch(
            candidate_text.strip()
        ):
            label_row = label_parts
            label_text = candidate_text
            break
        if candidate is not None:
            label_row = label_parts
            label_text = candidate_text
            observed_page_key = candidate
            break
    page_key = observed_page_key or fallback_key
    label_bbox = _merge_bbox(label_row) if label_row else None

    date_candidates: list[
        tuple[DocDate, str, tuple[float, float, float, float], Span]
    ] = []
    for row in visual_rows(spans):
        for start in range(len(row)):
            for end in range(start, min(len(row), start + 5)):
                date_text_candidate = _join_cell(row[start : end + 1])
                parsed_date = parse_date(date_text_candidate)
                if parsed_date is None:
                    continue
                date_spans = row[start : end + 1]
                date_candidates.append(
                    (
                        parsed_date,
                        date_text_candidate,
                        _merge_bbox(date_spans),
                        date_spans[0],
                    )
                )
    right_candidates = [
        candidate
        for candidate in date_candidates
        if candidate[3].bbox[0] > page_width / 2
    ]
    candidates = right_candidates or date_candidates
    date_value: DocDate | None = None
    date_text = ""
    date_bbox: tuple[float, float, float, float] | None = None
    date_span: Span | None = None
    if candidates:
        date_value, date_text, date_bbox, date_span = max(
            candidates,
            key=lambda candidate: (
                len(candidate[0].text),
                candidate[3].bbox[1],
            ),
        )
    return PageFooter(
        page=page.page,
        page_key=page_key,
        observed_page_key=observed_page_key,
        label_text=label_text,
        label_bbox=label_bbox,
        page_number_bbox=label_bbox if label_bbox is not None else _page_number_bbox(date_span),
        date=date_value,
        date_text=date_text,
        date_bbox=date_bbox,
    )


# --------------------------------------------------------------------------
# State assembly
# --------------------------------------------------------------------------


def _is_highlights_page(page: ParsedPage) -> bool:
    return (
        _highlights_header(visual_rows(page.spans)) is not None
        or _HIGHLIGHTS_TITLE_RE.search(page.text or "") is not None
    )


def _is_lep_page(page: ParsedPage) -> bool:
    if not _LEP_TITLE_RE.search(page.text or ""):
        return False
    return (
        _lep_header(visual_rows(page.spans)) is not None
        or _LEP_TITLE_LINE_RE.search(page.text or "") is not None
    )


def _is_ror_page(page: ParsedPage) -> bool:
    if page.spans:
        rows = visual_rows(page.spans)
        if not rows:
            return False
        min_y = min(span.bbox[1] for span in page.spans)
        max_y = max(span.bbox[3] for span in page.spans)
        title_bottom = min_y + (max_y - min_y) * 0.25
        return any(
            _ROR_TITLE_RE.fullmatch(_join_cell(row)) is not None
            and min(span.bbox[1] for span in row) <= title_bottom
            for row in rows
        )
    return any(
        _ROR_TITLE_RE.fullmatch(" ".join(line.split())) is not None
        for line in (page.text or "").splitlines()[:10]
    )


def _is_title_page(page: ParsedPage) -> bool:
    text = page.text or ""
    return (
        _TITLE_PAGE_RE.search(text) is not None
        and _TITLE_PAGE_ANCHOR_RE.search(text) is not None
        and not _is_highlights_page(page)
        and not _is_lep_page(page)
        and not _is_ror_page(page)
    )


def _special_footer_section(page: ParsedPage) -> str | None:
    if _is_highlights_page(page):
        return HIGHLIGHTS_KEY_PREFIX
    if _is_lep_page(page):
        return "LEP"
    if _is_ror_page(page):
        return "ROR"
    return None


def build_revision_state(parsed: ParsedPdf, document: object | None) -> RevisionState:
    """Extract the three sources and mark every parsed page as modified or not.

    Unmatched pages default to unchanged when all three revision sources are
    available. Contradictory declarations remain undecided. The first page of
    each revision section and Highlights Page 2 are always marked modified.
    """
    expected_footer_keys: dict[int, str] = {}
    section_numbers: dict[str, int] = {}
    first_section_pages: set[int] = set()
    title_pages: list[int] = []
    for page in parsed.pages:
        section = _special_footer_section(page)
        if section is not None:
            if section not in section_numbers:
                first_section_pages.add(page.page)
            section_numbers[section] = section_numbers.get(section, 0) + 1
            if section == HIGHLIGHTS_KEY_PREFIX and section_numbers[section] == 2:
                first_section_pages.add(page.page)
            expected_footer_keys[page.page] = f"{section} {section_numbers[section]}"
        elif page.page_type == "TP1" or _is_title_page(page):
            title_pages.append(page.page)
    for number, page_number in enumerate(title_pages, start=1):
        expected_footer_keys[page_number] = f"TP {number}"
    if title_pages:
        first_section_pages.add(title_pages[0])

    state = RevisionState(
        revision_date=parse_date(getattr(document, "meta_revision_date", None)),
        first_issue_date=parse_date(getattr(document, "meta_first_issue_date", None)),
        last_issue_date=parse_date(getattr(document, "meta_last_issue_date", None)),
        # `page_range.filter_pdf` keeps the original page numbers, so a run
        # restricted to a sub-range no longer starts at 1 / ends at the last
        # page. Absence controls must stay silent on such a run.
        full_document=bool(parsed.pages)
        and parsed.pages[0].page == 1
        and parsed.pages[-1].page == parsed.page_count,
        expected_footer_keys=expected_footer_keys,
    )
    highlights_pages: list[int] = []
    lep_pages: list[int] = []
    subject = ""
    for page in parsed.pages:
        fallback_key = expected_footer_keys.get(page.page)
        if _is_highlights_page(page):
            highlights_pages.append(page.page)
            state.highlights.extend(extract_highlights(page))
            state.invalid_highlights_designations.extend(
                extract_invalid_highlights_designations(page)
            )
            state.missing_highlights_designations.extend(
                extract_missing_highlights_designations(page)
            )
        elif _is_lep_page(page):
            lep_pages.append(page.page)
            entries, subject = extract_lep(page, subject)
            state.lep.extend(entries)
        if _is_ror_page(page):
            state.ror_entries.extend(extract_ror(page))
        footer = extract_footer(page, fallback_key)
        if footer is not None:
            state.footers.append(footer)
    state.highlights_pages = tuple(highlights_pages)
    state.lep_pages = tuple(lep_pages)
    footer_pages = {footer.page for footer in state.footers}
    state.missing_footer_pages = tuple(
        page.page
        for page in parsed.pages
        if page.page not in footer_pages
        and (bool(page.text.strip()) or page.page in expected_footer_keys)
    )

    _mark_modified_pages(parsed, state)
    for page in parsed.pages:
        if page.page in first_section_pages:
            page.is_modified = True
    state.findings = revision_findings(state)
    return state


def _mark_modified_pages(parsed: ParsedPdf, state: RevisionState) -> None:
    """Default unmatched pages to unchanged and reserve unknown for conflicts."""
    footer_by_page = {footer.page: footer for footer in state.footers}
    revision_date = state.revision_date
    if not state.available or revision_date is None:
        return

    for page in parsed.pages:
        page.is_modified = False

    for page in parsed.pages:
        footer = footer_by_page.get(page.page)
        if footer is None or footer.page_key is None or footer.date is None:
            continue
        lep_entry = state.lep_entry_for_key(footer.page_key)
        if lep_entry is None or lep_entry.date is None:
            continue

        status = state.highlights_status_for_lep(lep_entry)
        highlights_modified = status in _MODIFIED_STATUSES
        lep_modified = lep_entry.starred and revision_date.same_as(lep_entry.date)
        footer_modified = revision_date.same_as(footer.date)
        if highlights_modified and lep_modified and footer_modified:
            page.is_modified = True
            continue

        highlights_unchanged = status in {None, "U"}
        lep_unchanged = not lep_entry.starred and not revision_date.same_as(lep_entry.date)
        footer_unchanged = (
            not revision_date.same_as(footer.date)
            and lep_entry.date.same_as(footer.date)
        )
        if highlights_unchanged and lep_unchanged and footer_unchanged:
            page.is_modified = False
        else:
            page.is_modified = None


# --------------------------------------------------------------------------
# Cross-source controls
# --------------------------------------------------------------------------

# Identifiers carried by `Check.expected` (see `RevisionControl` in
# `app.core.compiled_rules`): one control = one compiled rule.
LEP_STAR = "lep_star"
UNDECLARED_STAR = "undeclared_star"
BLANK_LEP_STAR = "blank_lep_star"
LEP_DATE = "lep_date"
FOOTER_DATE = "footer_date"
HIGHLIGHTS_STATUS_CONSISTENCY = "highlights_status_consistency"
HIGHLIGHTS_DESIGNATION_REQUIRED = "highlights_designation_required"
UNDECLARED_PAGE = "undeclared_page"
PAGE_NOT_IN_LEP = "page_not_in_lep"
MODIFIED_PAGE_ABSENT = "modified_page_absent"
HIGHLIGHTS_PAIRING = "highlights_pairing"
HIGHLIGHTS_PAGE_LABEL = "highlights_page_label"
FOOTER_PAGE_NUMBER = "footer_page_number"
ROR_INSERTION_DATE = "ror_insertion_date"
ROR_REVISION_DATE = "ror_revision_date"

_PAGE_LABEL_RE = re.compile(r"(?i)^(?P<word>pages?)(?P<gap>\s+)(?P<rest>\S.*)$")
_MULTIPLE_PAGE_NUMBERS_RE = re.compile(
    r"(?i)^(?P<prefix>.*?\bpages?)\s+(?P<first>\d+(?:-\d+)?)"
    r"\s*/\s*\d+(?:-\d+)?$"
)
_PAGE_LABEL_ALIGNMENT_TOLERANCE = 2.0


@dataclass(frozen=True)
class RevisionFinding:
    control: str
    message: str
    original: str
    proposed: str
    page: int
    bbox: tuple[float, float, float, float] | None
    severity: Literal["info", "warning", "error"] | None = None


def _context(subject: str, page_key: str) -> str:
    return f"« {subject} », page {page_key}" if subject else f"page {page_key}"


def _highlights_status_conflict_for_page(
    state: RevisionState,
    page_key: str,
    status: str | None,
) -> str | None:
    revision = state.revision_date
    lep_entry = state.lep_entry_for_key(page_key)
    footer = state.footer_by_key.get(page_key)
    if revision is None or lep_entry is None or footer is None or lep_entry.is_blank:
        return None

    context = _context(lep_entry.subject, page_key)
    if status == "U":
        if (
            lep_entry.starred
            and revision.same_as(lep_entry.date)
            and revision.same_as(footer.date)
        ):
            return (
                f"{context} : la LEP porte une étoile et la date "
                f"{lep_entry.date_text}, et le pied de page porte {footer.date_text}."
            )
        return None

    if status not in _MODIFIED_STATUSES:
        return None
    previous_issue = state.last_issue_date or revision
    if (
        lep_entry.starred
        or lep_entry.date is None
        or footer.date is None
        or revision.same_as(lep_entry.date)
        or not lep_entry.date.same_as(footer.date)
        or lep_entry.date.sort_key > previous_issue.sort_key
    ):
        return None
    return (
        f"{context} : la LEP ne porte pas d'étoile et sa date {lep_entry.date_text} "
        f"correspond au pied de page {footer.date_text}, antérieur à la révision courante."
    )


def _lep_findings(state: RevisionState) -> list[RevisionFinding]:
    revision = state.revision_date
    assert revision is not None  # guarded by RevisionState.available
    findings: list[RevisionFinding] = []
    for entry in state.lep:
        status = state.highlights_status_for_lep(entry)
        context = _context(entry.subject, entry.page_key)

        if entry.is_blank:
            page_number = page_number_of(entry.page_key)
            if page_number is not None:
                odd_page_number = page_number if page_number % 2 else page_number - 1
                prefix = page_key_prefix(entry.page_key)
                odd_page_key = (
                    f"{prefix} {odd_page_number}" if prefix else str(odd_page_number)
                )
                should_be_starred = state.highlights_status_for_lep(entry, odd_page_key) == "N"
                if entry.starred != should_be_starred:
                    if should_be_starred:
                        message = (
                            f"{context} est une page Blank dont la page impaire "
                            f"{odd_page_key} est déclarée New (N) dans les Highlights : "
                            "sa date doit être suivie de « * » dans la LEP."
                        )
                        proposed = f"{entry.date_text.rstrip()} *"
                    else:
                        message = (
                            f"{context} est une page Blank dont la page impaire "
                            f"{odd_page_key} n'est pas déclarée New (N) dans les "
                            "Highlights : elle ne doit pas porter de « * » dans la LEP."
                        )
                        proposed = entry.date_text.replace("*", "").rstrip()
                    findings.append(
                        RevisionFinding(
                            control=BLANK_LEP_STAR,
                            message=message,
                            original=entry.date_text,
                            proposed=proposed,
                            page=entry.page,
                            bbox=entry.bbox,
                        )
                    )
            continue

        declared = status in _MODIFIED_STATUSES or status == "D"
        status_conflict = _highlights_status_conflict_for_page(
            state, entry.page_key, status
        )

        if declared and not entry.starred:
            if status_conflict:
                message = (
                    f"{context} est déclarée « {status} » dans les Highlights sans "
                    f'étoile dans la LEP, mais {status_conflict} Le contrôle '
                    "« CUSTOM_REVISION_HIGHLIGHTS_STATUS » indique que le statut "
                    "est peut-être U. Vérifier les Highlights avant d'ajouter « * »."
                )
            else:
                message = (
                    f"{context} est marquée « {status} » dans les Highlights "
                    "mais sa date n'est pas suivie de « * » dans la LEP."
                )
            findings.append(
                RevisionFinding(
                    control=LEP_STAR,
                    message=message,
                    original=entry.date_text,
                    proposed="" if status_conflict else f"{entry.date_text} *",
                    page=entry.page,
                    bbox=entry.bbox,
                    severity="info" if status_conflict else None,
                )
            )
            continue
        if not declared and entry.starred:
            designation_rule = state.highlights_designation_rule_for(entry)
            if designation_rule:
                designation_state = (
                    "absente"
                    if designation_rule == "CUSTOM_HIGHLIGHTS_DESIGNATION_REQUIRED"
                    else "invalide"
                )
                message = (
                    f"{context} porte une « * » dans la LEP, mais sa désignation "
                    f"est {designation_state} dans les Highlights. La règle "
                    f"« {designation_rule} » l'a détectée : le statut R/N est "
                    "inconnu et l'étoile peut être justifiée. Vérifier les "
                    "Highlights avant de la retirer."
                )
            elif status_conflict:
                message = (
                    f"{context} porte une « * » dans la LEP, mais {status_conflict} "
                    "Le contrôle « CUSTOM_REVISION_HIGHLIGHTS_STATUS » signale une "
                    "contradiction; vérifier si la désignation doit être R ou N "
                    "avant de retirer l'étoile."
                )
            else:
                observed = f"« {status} »" if status else "absente des Highlights"
                message = (
                    f"{context} porte une « * » dans la LEP alors qu'elle est "
                    f"{observed} : la page doit être déclarée R ou N, ou la "
                    "« * » doit être retirée."
                )
            findings.append(
                RevisionFinding(
                    control=UNDECLARED_STAR,
                    message=message,
                    original=entry.date_text,
                    proposed=(
                        ""
                        if designation_rule or status_conflict
                        else entry.date_text.replace("*", "").rstrip()
                    ),
                    page=entry.page,
                    bbox=entry.bbox,
                    severity="info" if designation_rule or status_conflict else None,
                )
            )
            continue
        if status == "D":
            continue

        if declared:
            if not revision.same_as(entry.date):
                findings.append(
                    RevisionFinding(
                        control=LEP_DATE,
                        message=(
                            f"{context} est révisée : la LEP doit porter la date de "
                            f"révision {revision.text}, et non « {entry.date_text} »."
                        ),
                        original=entry.date_text,
                        proposed=f"{revision.text} *",
                        page=entry.page,
                        bbox=entry.bbox,
                    )
                )
            continue

        if revision.same_as(entry.date):
            designation_rule = state.highlights_designation_rule_for(entry)
            message = (
                f"{context} porte la date de révision {revision.text} dans la "
                "LEP mais n'est déclarée modifiée ni dans les Highlights "
                "(R ou N) ni par une « * »."
            )
            if designation_rule:
                designation_state = (
                    "absente"
                    if designation_rule == "CUSTOM_HIGHLIGHTS_DESIGNATION_REQUIRED"
                    else "invalide"
                )
                message = (
                    f"{message} La désignation Highlights de cette page est "
                    f"{designation_state} ({designation_rule}); cela peut expliquer "
                    "l'absence du statut R/N, mais la date de révision dans la LEP "
                    "reste un indice indépendant à vérifier."
                )
            findings.append(
                RevisionFinding(
                    control=UNDECLARED_PAGE,
                    message=message,
                    original=entry.date_text,
                    proposed="",
                    page=entry.page,
                    bbox=entry.bbox,
                )
            )
        elif (
            entry.date is not None
            and state.last_issue_date is not None
            and entry.date.sort_key > state.last_issue_date.sort_key
        ):
            findings.append(
                RevisionFinding(
                    control=LEP_DATE,
                    message=(
                        f"{context} est inchangée mais sa date LEP « {entry.date_text} » "
                        "est postérieure à la dernière issue connue "
                        f"({state.last_issue_date.text})."
                    ),
                    original=entry.date_text,
                    proposed="",
                    page=entry.page,
                    bbox=entry.bbox,
                )
            )
    return findings


def _highlights_status_findings(state: RevisionState) -> list[RevisionFinding]:
    footer_by_key = state.footer_by_key
    findings: list[RevisionFinding] = []

    for entry in state.highlights:
        if entry.status == "D":
            present_in_lep = [
                key
                for key in entry.page_keys
                if any(
                    not lep_entry.is_blank
                    and not _DELETED_LEP_RE.match(lep_entry.date_text)
                    for lep_entry in state.lep_entries_for_key(key)
                )
            ]
            present_in_document = [
                key for key in entry.page_keys if key in footer_by_key
            ]
            present = sorted(set(present_in_lep + present_in_document))
            if not present:
                continue
            findings.append(
                RevisionFinding(
                    control=HIGHLIGHTS_STATUS_CONSISTENCY,
                    message=(
                        f"Les Highlights déclarent « {entry.pages_text} » comme "
                        f"supprimée (D), mais {', '.join(present)} figure encore "
                        "dans la LEP ou le document courant."
                    ),
                    original=entry.status,
                    proposed="",
                    page=entry.page,
                    bbox=entry.status_bbox,
                )
            )
            continue
        if entry.status not in _MODIFIED_STATUSES | {"U"}:
            continue
        conflicting_pages: list[str] = []
        for page_key in entry.page_keys:
            conflict = _highlights_status_conflict_for_page(
                state, page_key, entry.status
            )
            if conflict:
                conflicting_pages.append(conflict)

        if not conflicting_pages:
            continue
        if entry.status == "U":
            message = (
                f"Les Highlights déclarent « U » (inchangée), mais "
                f"{'; '.join(conflicting_pages)} Ces marqueurs indiquent une page "
                "modifiée. Vérifier la désignation; sans la LEP précédente, le "
                "moteur ne peut pas choisir entre « R » et « N »."
            )
        else:
            message = (
                f"Les Highlights déclarent « {entry.status} » "
                f"({'révisée' if entry.status == 'R' else 'nouvelle'}), mais "
                f"{'; '.join(conflicting_pages)} Ces marqueurs indiquent une page "
                "inchangée. Vérifier la désignation (probablement « U » si la LEP "
                "et le pied de page sont corrects)."
            )
        findings.append(
            RevisionFinding(
                control=HIGHLIGHTS_STATUS_CONSISTENCY,
                message=message,
                original=entry.status,
                proposed="",
                page=entry.page,
                bbox=entry.status_bbox,
            )
        )
    return findings


def _highlights_previous_revision_findings(
    current: RevisionState,
    previous: RevisionState,
) -> list[RevisionFinding]:
    """Check Highlights designations against pages in the previous LEP."""
    if not previous.lep:
        return []

    findings: list[RevisionFinding] = []
    for entry in current.highlights:
        if _LEP_TITLE_RE.search(entry.subject):
            continue
        page_keys = [
            key for key in entry.page_keys
            if page_key_prefix(key) != "LEP"
        ]
        if not page_keys or entry.status not in _HIGHLIGHTS_STATUSES:
            continue

        previous_presence = {
            key: _previous_lep_page_presence(previous, key)
            for key in page_keys
        }
        if entry.status == "N":
            conflicting_pages = sorted(
                key for key, present in previous_presence.items() if present is True
            )
            expected = "R ou U"
            detail = "figure déjà dans la LEP N-1"
        else:
            conflicting_pages = sorted(
                key for key, present in previous_presence.items() if present is False
            )
            expected = "N" if entry.status in {"R", "U"} else "une page présente en N-1"
            detail = "ne figure pas dans la LEP N-1"
        if not conflicting_pages:
            continue

        findings.append(
            RevisionFinding(
                control=HIGHLIGHTS_STATUS_CONSISTENCY,
                message=(
                    f"La désignation « {entry.status} » des Highlights pour "
                    f"« {entry.pages_text} » est incohérente avec la LEP N-1 : "
                    f"{', '.join(conflicting_pages)} {detail}. "
                    f"Vérifier la désignation (attendu : {expected})."
                ),
                original=entry.status,
                proposed="",
                page=entry.page,
                bbox=entry.status_bbox,
            )
        )
    return findings


def _previous_lep_page_presence(previous: RevisionState, page_key: str) -> bool | None:
    entries = previous.lep_entries_for_key(page_key)
    if len(entries) > 1:
        return None
    if not entries:
        return False
    entry = entries[0]
    return not entry.is_blank and not _DELETED_LEP_RE.match(entry.date_text)


def _invalid_highlights_designation_findings(
    state: RevisionState,
) -> list[RevisionFinding]:
    return [
        RevisionFinding(
            control=HIGHLIGHTS_STATUS_CONSISTENCY,
            message=(
                f"La désignation « {issue.designation} » des Highlights pour "
                f"« {issue.pages_text} » n'est pas valide. Valeurs autorisées : "
                "R, N, U ou D."
            ),
            original=issue.designation,
            proposed="",
            page=issue.page,
            bbox=issue.bbox,
        )
        for issue in state.invalid_highlights_designations
    ]


def _missing_highlights_designation_findings(
    state: RevisionState,
) -> list[RevisionFinding]:
    return [
        RevisionFinding(
            control=HIGHLIGHTS_DESIGNATION_REQUIRED,
            message=(
                f"La ligne des Highlights pour « {issue.pages_text} » "
                "ne comporte pas de désignation (R, N, U ou D)."
            ),
            original="",
            proposed="",
            page=issue.page,
            bbox=issue.bbox,
        )
        for issue in state.missing_highlights_designations
    ]


def _footer_findings(state: RevisionState) -> list[RevisionFinding]:
    revision = state.revision_date
    assert revision is not None
    findings: list[RevisionFinding] = []
    for footer in state.footers:
        page_key = state.expected_footer_keys.get(footer.page, footer.page_key)
        if page_key is None:
            continue
        if page_key_prefix(page_key) == HIGHLIGHTS_KEY_PREFIX:
            continue
        entries = state.lep_entries_for_key(page_key)

        if not entries:
            if state.full_document:
                findings.append(
                    RevisionFinding(
                        control=PAGE_NOT_IN_LEP,
                        message=(
                            f"La page « {footer.label_text} » est présente dans le "
                            "document mais absente de la liste des pages effectives."
                        ),
                        original=footer.label_text,
                        proposed="",
                        page=footer.page,
                        bbox=footer.label_bbox or footer.page_number_bbox,
                    )
                )
            continue
        if len(entries) > 1:
            continue
        entry = entries[0]
        declared = state.is_declared_modified(page_key)

        if state.is_contested(page_key):
            continue
        expected = revision if declared else entry.date
        if expected is None or expected.same_as(footer.date):
            continue
        if not declared and revision.same_as(footer.date):
            findings.append(
                RevisionFinding(
                    control=UNDECLARED_PAGE,
                    message=(
                        f"Le pied de page de « {footer.label_text} » porte la date de "
                        f"révision {revision.text} alors que la page n'est déclarée "
                        "modifiée ni dans les Highlights ni dans la LEP."
                    ),
                    original=footer.date_text,
                    proposed=expected.text,
                    page=footer.page,
                    bbox=footer.date_bbox,
                )
            )
            continue
        reason = (
            f"la date de révision {expected.text}"
            if declared
            else f"la dernière date d'émission connue {expected.text} (LEP)"
        )
        status = state.highlights_status_for_lep(entry, page_key)
        status_conflict = _highlights_status_conflict_for_page(
            state, page_key, status
        )
        message = (
            f"Le pied de page de « {footer.label_text} » porte "
            f"« {footer.date_text or 'aucune date'} » au lieu de {reason}."
        )
        if status_conflict:
            message = (
                f"{message} Le contrôle « CUSTOM_REVISION_HIGHLIGHTS_STATUS » "
                f"signale une contradiction : {status_conflict} Vérifier le statut "
                "Highlights avant de corriger cette date."
            )
        findings.append(
            RevisionFinding(
                control=FOOTER_DATE,
                message=message,
                original=footer.date_text or footer.label_text,
                proposed="" if status_conflict else expected.text,
                page=footer.page,
                bbox=footer.date_bbox,
                severity="info" if status_conflict else None,
            )
        )
    return findings


def _display_page_key(page_key: str) -> str:
    prefix, _, number = page_key.partition(" ")
    if prefix == "TP":
        return f"TP {number}"
    if prefix == "HIGHLIGHTS":
        return f"Highlights Page {number}"
    if prefix in {"LEP", "ROR"}:
        return f"{prefix} Page {number}"
    if prefix:
        return f"{prefix.title()} Page {number}"
    return f"Page {number}"


def _footer_page_number_findings(state: RevisionState) -> list[RevisionFinding]:
    """Require a readable page identifier in every detected footer.

    Section pages have a deterministic expected key from their title and
    physical order. Title pages use the same order for TP 1 / TP 2 because
    their visible heading is identical; the LEP then confirms those keys.
    Other pages only need a parseable footer label here. Their exact
    membership in the LEP remains the responsibility of PAGE_NOT_IN_LEP.
    """
    findings: list[RevisionFinding] = []
    expected = state.expected_footer_keys

    for page in state.missing_footer_pages:
        expected_key = expected.get(page)
        if expected_key is None:
            message = f"La page {page} ne contient pas de pied de page identifiable."
            proposed = ""
        else:
            display = _display_page_key(expected_key)
            message = (
                f"La page {page} ne contient pas le numero de page attendu "
                f"« {display} » dans son pied de page."
            )
            proposed = display
        findings.append(
            RevisionFinding(
                control=FOOTER_PAGE_NUMBER,
                message=message,
                original="",
                proposed=proposed,
                page=page,
                bbox=None,
            )
        )

    for footer in state.footers:
        expected_key = expected.get(footer.page)
        multiple_numbers = _MULTIPLE_PAGE_NUMBERS_RE.fullmatch(
            footer.label_text.strip()
        )
        if multiple_numbers is not None:
            prefix = re.sub(
                r"(?i)\bpages?$",
                "Page",
                multiple_numbers.group("prefix").strip(),
            )
            proposed = (
                _display_page_key(expected_key)
                if expected_key is not None
                else f"{prefix} {multiple_numbers.group('first')}"
            )
            findings.append(
                RevisionFinding(
                    control=FOOTER_PAGE_NUMBER,
                    message=(
                        f"Le pied de page doit contenir un seul numero : "
                        f"« {footer.label_text} » doit devenir « {proposed} »."
                    ),
                    original=footer.label_text,
                    proposed=proposed,
                    page=footer.page,
                    bbox=footer.label_bbox,
                )
            )
            continue
        if expected_key is not None:
            if footer.observed_page_key == expected_key:
                continue
            display = _display_page_key(expected_key)
            findings.append(
                RevisionFinding(
                    control=FOOTER_PAGE_NUMBER,
                    message=(
                        f"Le pied de page de la page {footer.page} porte "
                        f"« {footer.label_text or 'aucun numero'} » au lieu de "
                        f"« {display} »."
                    ),
                    original=footer.label_text if footer.observed_page_key else "",
                    proposed=display,
                    page=footer.page,
                    bbox=footer.page_number_bbox,
                )
            )
            continue
        if footer.observed_page_key is None:
            findings.append(
                RevisionFinding(
                    control=FOOTER_PAGE_NUMBER,
                    message=(
                        f"Le pied de page de la page {footer.page} ne contient "
                        "aucun numero de page."
                    ),
                    original="",
                    proposed="",
                    page=footer.page,
                    bbox=footer.page_number_bbox,
                )
            )

    return findings


def _missing_page_findings(state: RevisionState) -> list[RevisionFinding]:
    if not state.full_document:
        return []
    found = set(state.footer_by_key)
    lep = state.lep_by_key
    unlabeled_pages = {
        footer.page for footer in state.footers if footer.observed_page_key is None
    }
    unlabeled_pages.update(state.missing_footer_pages)
    findings: list[RevisionFinding] = []
    for entry in state.highlights:
        if entry.status not in _MODIFIED_STATUSES:
            continue
        missing = [
            key
            for key in entry.page_keys
            if key not in found and not (key in lep and lep[key].is_blank)
        ]
        if not missing:
            continue
        # A physical page with a footer block but no readable identifier is
        # handled by FOOTER_PAGE_NUMBER, not reported again as absent.
        if unlabeled_pages:
            missing = missing[len(unlabeled_pages) :]
        if not missing:
            continue
        findings.append(
            RevisionFinding(
                control=MODIFIED_PAGE_ABSENT,
                message=(
                    f"Les Highlights déclarent « {entry.pages_text} » ({entry.status}) "
                    f"mais aucune page du document ne s'identifie comme "
                    f"{', '.join(missing)} dans son pied de page."
                ),
                original=entry.pages_text,
                proposed="",
                page=entry.page,
                bbox=entry.bbox,
            )
        )
    return findings


def _pairing_findings(state: RevisionState) -> list[RevisionFinding]:
    listed = {key for entry in state.highlights for key in entry.page_keys}
    findings: list[RevisionFinding] = []
    for entry in state.highlights:
        missing: list[str] = []
        for key in entry.page_keys:
            number = page_number_of(key)
            if number is None:
                continue
            prefix = page_key_prefix(key)
            neighbour = number + 1 if number % 2 else number - 1
            expected = f"{prefix} {neighbour}" if prefix else str(neighbour)
            if expected in listed or expected in missing:
                continue
            missing.append(expected)
        if not missing:
            continue
        findings.append(
            RevisionFinding(
                control=HIGHLIGHTS_PAIRING,
                message=(
                    f"Les Highlights listent « {entry.pages_text} » sans sa contrepartie "
                    f"{', '.join(missing)} : les pages doivent être déclarées par couple "
                    "impaire/paire, la page paire suivant immédiatement l'impaire."
                ),
                original=entry.pages_text,
                proposed="",
                page=entry.page,
                bbox=entry.bbox,
            )
        )
    return findings


def _page_label_findings(state: RevisionState) -> list[RevisionFinding]:
    reference_positions = []
    for entry in state.highlights:
        match = _PAGE_LABEL_RE.match(entry.pages_text)
        if match is None or entry.page_number_x is None:
            continue
        multiple = len(entry.page_keys) > 1
        label = "Pages" if multiple else "Page"
        expected = f"{label}{' ' if multiple else '  '}{match.group('rest')}"
        if entry.pages_text == expected:
            reference_positions.append(entry.page_number_x)
    reference_x = (
        sorted(reference_positions)[len(reference_positions) // 2]
        if reference_positions
        else None
    )

    findings: list[RevisionFinding] = []
    for entry in state.highlights:
        match = _PAGE_LABEL_RE.match(entry.pages_text)
        if match is None:
            continue
        multiple = len(entry.page_keys) > 1
        label = "Pages" if multiple else "Page"
        # A single page is written « Page » plus two spaces so its number
        # stays aligned with the numbers of the « Pages » rows.
        expected = f"{label}{' ' if multiple else '  '}{match.group('rest')}"
        word_matches = match.group("word").casefold() == label.casefold()
        visually_aligned = (
            word_matches
            and entry.page_number_x is not None
            and reference_x is not None
            and abs(entry.page_number_x - reference_x)
            <= _PAGE_LABEL_ALIGNMENT_TOLERANCE
        )
        if entry.pages_text == expected or visually_aligned:
            continue
        findings.append(
            RevisionFinding(
                control=HIGHLIGHTS_PAGE_LABEL,
                message=(
                    f"Les Highlights notent « {entry.pages_text} » au lieu de "
                    f"« {expected} »."
                ),
                original=entry.pages_text,
                proposed=expected,
                page=entry.page,
                bbox=entry.bbox,
            )
        )
    return findings


def _expected_ror_insertion_date(revision_date: DocDate) -> DocDate:
    month = revision_date.month
    if revision_date.day is None or revision_date.day >= 15:
        month += 1
    year = revision_date.year
    if month > 12:
        month = 1
        year += 1
    return DocDate(
        month=month,
        day=None,
        year=year,
        text=f"{_MONTHS[month - 1]} {year % 100:02d}",
    )


def _ror_insertion_findings(state: RevisionState) -> list[RevisionFinding]:
    findings: list[RevisionFinding] = []
    for entry in state.ror_entries:
        if entry.revision_date is None:
            continue
        expected = _expected_ror_insertion_date(entry.revision_date)
        observed = entry.insertion_date
        if (
            observed is not None
            and observed.day is None
            and observed.month == expected.month
            and observed.year == expected.year
        ):
            continue
        if observed is None:
            message = (
                f"La date d'insertion du ROR est absente pour la date de revision "
                f"{entry.revision_date.text} : elle doit etre {expected.text}."
            )
        else:
            message = (
                f"La date d'insertion « {entry.insertion_date_text} » du ROR est "
                f"incorrecte pour la date de revision {entry.revision_date.text} : "
                f"elle doit etre {expected.text}."
            )
        findings.append(
            RevisionFinding(
                control=ROR_INSERTION_DATE,
                message=message,
                original=entry.insertion_date_text,
                proposed=expected.text,
                page=entry.page,
                bbox=entry.bbox,
            )
        )
    return findings


def _ror_revision_findings(state: RevisionState) -> list[RevisionFinding]:
    expected = state.revision_date
    dated_entries = [
        entry for entry in state.ror_entries if entry.revision_date is not None
    ]
    if expected is None or not dated_entries:
        return []
    current = max(
        dated_entries,
        key=lambda entry: (
            entry.revision_date.sort_key
            if entry.revision_date is not None
            else (0, 0, 0)
        ),
    )
    if current.revision_date is None or current.revision_date.same_as(expected):
        return []
    return [
        RevisionFinding(
            control=ROR_REVISION_DATE,
            message=(
                f"La date de revision « {current.revision_date_text} » du ROR "
                f"ne correspond pas a la date des Highlights « {expected.text} »."
            ),
            original=current.revision_date_text,
            proposed=expected.text,
            page=current.page,
            bbox=current.bbox,
        )
    ]


def revision_findings(state: RevisionState) -> list[RevisionFinding]:
    """Cross-check Highlights, LEP and footers, one finding per divergence."""
    findings: list[RevisionFinding] = (
        _missing_highlights_designation_findings(state)
        + _invalid_highlights_designation_findings(state)
        + _highlights_status_findings(state)
    )
    if state.available:
        findings.extend(
            _lep_findings(state)
            + _footer_findings(state)
            + _footer_page_number_findings(state)
            + _missing_page_findings(state)
            + _pairing_findings(state)
            + _page_label_findings(state)
        )
    findings.extend(_ror_insertion_findings(state))
    findings.extend(_ror_revision_findings(state))
    return sorted(findings, key=lambda finding: (finding.page, finding.control))


def findings_for(state: RevisionState, control: str) -> list[RevisionFinding]:
    return [finding for finding in state.findings if finding.control == control]
