"""Cross-source detection of the pages revised by a THALES revision.

Three sources describe the same fact — « which pages did this revision
touch » — and they must agree before any other control is worth running:

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
from dataclasses import dataclass, field

from app.parsers.pdf_parser import ParsedPage, ParsedPdf, Span


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
_ROR_TITLE_RE = re.compile(r"(?im)^\s*(?:record\s+of\s+revisions?|ror)\s*$")
_TITLE_PAGE_RE = re.compile(r"(?im)^\s*overhaul\s+manual\s*$")
_TITLE_PAGE_ANCHOR_RE = re.compile(
    r"(?im)^\s*(?:first\s+issue\s*:|part\s+number|important\s+notice)\b"
)
_LEP_HEADER_CELLS = ("SUBJECT", "PAGE", "DATE")

_COPYRIGHT_ANCHOR_RE = re.compile(r"(?i)THALES\s+AVS\s+FRANCE")
HIGHLIGHTS_KEY_PREFIX = "HIGHLIGHTS"
# Any section abbreviation, not a closed list: manuals introduce new ones
# (TP, ROR, LEP, TC, INTRO, SB, LOI...). « Page(s) » is the generic word and
# a month name starts a date, so neither can be a prefix.
_NOT_A_PREFIX = "|".join(("PAGES?",) + _MONTHS)
_PAGE_KEY_RE = re.compile(
    rf"(?i)^(?:(?!(?:{_NOT_A_PREFIX})\b)(?P<prefix>[A-Z]{{2,12}})\s+)?"
    r"(?:pages?\s+)?(?P<number>\d+(?:-\d+)?)$"
)
_RANGE_SPLIT_RE = re.compile(r"(?i)\s+(?:to|thru|through)\s+|\s*(?:-|–|—)\s*(?=\d)")
_BLANK_RE = re.compile(r"(?i)^blank\b")


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


@dataclass(frozen=True)
class PageFooter:
    page: int
    page_key: str | None
    observed_page_key: str | None
    label_text: str
    label_bbox: tuple[float, float, float, float] | None
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
    lep: list[LepEntry] = field(default_factory=list)
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
        for entry in self.highlights:
            for key in entry.page_keys:
                statuses.setdefault(key, entry.status)
        return statuses

    @property
    def lep_by_key(self) -> dict[str, LepEntry]:
        entries: dict[str, LepEntry] = {}
        for entry in self.lep:
            entries.setdefault(entry.page_key, entry)
        return entries

    @property
    def footer_by_key(self) -> dict[str, PageFooter]:
        footers: dict[str, PageFooter] = {}
        for footer in self.footers:
            if footer.page_key is not None:
                footers.setdefault(footer.page_key, footer)
        return footers

    def is_declared_modified(self, page_key: str) -> bool:
        if self.status_by_key.get(page_key) in _MODIFIED_STATUSES:
            return True
        entry = self.lep_by_key.get(page_key)
        return entry is not None and entry.starred

    def is_contested(self, page_key: str) -> bool:
        """Whether the star and the Highlights status disagree on this page.

        The star then has no trustworthy expected date behind it, so the
        footer control stays silent until the contradiction is resolved.
        """
        entry = self.lep_by_key.get(page_key)
        if entry is None or not entry.starred:
            return False
        return self.status_by_key.get(page_key) not in _MODIFIED_STATUSES | {"D"}


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
    match = _DATE_RE.search(value)
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
    compact = " ".join(value.split())
    match = _PAGE_KEY_RE.match(compact)
    if match is None:
        return None
    prefix = match.group("prefix")
    number = match.group("number")
    return f"{prefix.upper()} {number}" if prefix else number


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
    # « Page 701 to 704 »: the second bound inherits the first one's prefix.
    if not end_prefix:
        end_prefix = start_prefix
    if start_prefix != end_prefix or not start_number.isdigit() or not end_number.isdigit():
        return (start_key, end_key)
    first, last = int(start_number), int(end_number)
    if last < first or last - first > 500:
        return (start_key, end_key)
    return tuple(
        f"{start_prefix} {number}" if start_prefix else str(number)
        for number in range(first, last + 1)
    )


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


def _highlights_header(rows: list[list[Span]]) -> tuple[int, float, float] | None:
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
        return index, pages_max, status_max
    return None


def extract_highlights(page: ParsedPage) -> list[HighlightsEntry]:
    """Read one Highlights page into (subject, page range, status) entries."""
    rows = visual_rows(page.spans)
    header = _highlights_header(rows)
    if header is None:
        return []
    header_index, pages_max, status_max = header

    entries: list[HighlightsEntry] = []
    subject = ""
    pending: list[str] = []
    previous_was_subject = False
    for row in rows[header_index + 1 :]:
        pages_cells = [span for span in row if span.bbox[0] < pages_max]
        status_cells = [
            span
            for span in row
            if pages_max <= span.bbox[0] < status_max
            and span.text.strip().upper() in _HIGHLIGHTS_STATUSES
        ]
        if not pages_cells:
            previous_was_subject = False
            continue
        if not status_cells:
            if not previous_was_subject:
                pending = []
            pending.append(_join_cell(pages_cells))
            subject = _join_subject(pending)
            previous_was_subject = True
            continue
        previous_was_subject = False
        pages_text = _join_raw_cell(pages_cells)
        entries.append(
            HighlightsEntry(
                subject=subject,
                pages_text=pages_text,
                page_keys=expand_page_range(pages_text),
                status=status_cells[0].text.strip().upper(),
                page=page.page,
                bbox=_merge_bbox(pages_cells),
                status_bbox=status_cells[0].bbox,
            )
        )
    return entries


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

        if subject_cells:
            if not subject_continues:
                pending = []
            pending.append(_join_cell(subject_cells))
            subject_continues = True
        else:
            subject_continues = False
        if pending:
            subject = _join_subject(pending)

        if not page_cells or not date_cells:
            continue
        # A subject line sharing its row with an entry only wraps onto the
        # next row when it reads unfinished; otherwise the next subject line
        # starts a new section (« Cleaning » then « Inspection »).
        if subject_continues:
            subject_continues = pending[-1].rstrip().endswith(("-", ","))

        page_key = normalize_page_key(
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
            date=None,
            date_text="",
            date_bbox=None,
        )
    page_width = max(span.bbox[2] for span in page.spans)
    label_span = next(
        (span for span in spans if normalize_page_key(span.text) is not None),
        None,
    )
    observed_page_key = normalize_page_key(label_span.text) if label_span else None
    page_key = observed_page_key or fallback_key
    label_text = (
        " ".join(label_span.text.split())
        if label_span is not None
        else ""
    )

    date_spans = [span for span in spans if parse_date(span.text) is not None]
    right_spans = [span for span in date_spans if span.bbox[0] > page_width / 2]
    candidates = right_spans or date_spans
    date_span = max(candidates, key=lambda span: span.bbox[1], default=None)
    return PageFooter(
        page=page.page,
        page_key=page_key,
        observed_page_key=observed_page_key,
        label_text=label_text,
        label_bbox=label_span.bbox if label_span is not None else None,
        date=parse_date(date_span.text) if date_span is not None else None,
        date_text=" ".join(date_span.text.split()) if date_span is not None else "",
        date_bbox=date_span.bbox if date_span is not None else None,
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
    return _ROR_TITLE_RE.search(page.text or "") is not None


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


def build_revision_state(parsed: ParsedPdf, document: object) -> RevisionState:
    """Extract the three sources and mark every parsed page as modified or not.

    Pages the state cannot decide on (blank versos, the Highlights sheet
    itself) keep ``is_modified = None`` so rules scoped to modified pages
    still run on them instead of silently disappearing.
    """
    expected_footer_keys: dict[int, str] = {}
    section_numbers: dict[str, int] = {}
    title_pages: list[int] = []
    for page in parsed.pages:
        section = _special_footer_section(page)
        if section is not None:
            section_numbers[section] = section_numbers.get(section, 0) + 1
            expected_footer_keys[page.page] = f"{section} {section_numbers[section]}"
        elif _is_title_page(page):
            title_pages.append(page.page)
    for number, page_number in enumerate(title_pages, start=1):
        expected_footer_keys[page_number] = f"TP {number}"

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
        elif _is_lep_page(page):
            lep_pages.append(page.page)
            entries, subject = extract_lep(page, subject)
            state.lep.extend(entries)
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

    if state.available:
        _mark_modified_pages(parsed, state)
    state.findings = revision_findings(state)
    return state


def _mark_modified_pages(parsed: ParsedPdf, state: RevisionState) -> None:
    footer_by_page = {footer.page: footer for footer in state.footers}
    known_keys = set(state.lep_by_key) | set(state.status_by_key)
    for page in parsed.pages:
        footer = footer_by_page.get(page.page)
        if footer is None or page_key_prefix(footer.page_key) == HIGHLIGHTS_KEY_PREFIX:
            continue
        if footer.page_key not in known_keys:
            continue
        page.is_modified = state.is_declared_modified(footer.page_key)


# --------------------------------------------------------------------------
# Cross-source controls
# --------------------------------------------------------------------------

# Identifiers carried by `Check.expected` (see `RevisionControl` in
# `app.core.compiled_rules`): one control = one compiled rule.
LEP_STAR = "lep_star"
UNDECLARED_STAR = "undeclared_star"
LEP_DATE = "lep_date"
FOOTER_DATE = "footer_date"
UNDECLARED_PAGE = "undeclared_page"
PAGE_NOT_IN_LEP = "page_not_in_lep"
MODIFIED_PAGE_ABSENT = "modified_page_absent"
HIGHLIGHTS_PAIRING = "highlights_pairing"
HIGHLIGHTS_PAGE_LABEL = "highlights_page_label"
FOOTER_PAGE_NUMBER = "footer_page_number"

_PAGE_LABEL_RE = re.compile(r"(?i)^(?P<word>pages?)(?P<gap>\s+)(?P<rest>\S.*)$")


@dataclass(frozen=True)
class RevisionFinding:
    control: str
    message: str
    original: str
    proposed: str
    page: int
    bbox: tuple[float, float, float, float] | None


def _context(subject: str, page_key: str) -> str:
    return f"« {subject} », page {page_key}" if subject else f"page {page_key}"


def _lep_findings(state: RevisionState) -> list[RevisionFinding]:
    revision = state.revision_date
    assert revision is not None  # guarded by RevisionState.available
    statuses = state.status_by_key
    findings: list[RevisionFinding] = []
    for entry in state.lep:
        status = statuses.get(entry.page_key)
        context = _context(entry.subject, entry.page_key)
        declared = status in _MODIFIED_STATUSES or status == "D"

        if declared and not entry.starred:
            findings.append(
                RevisionFinding(
                    control=LEP_STAR,
                    message=(
                        f"{context} est marquée « {status} » dans les Highlights "
                        "mais sa date n'est pas suivie de « * » dans la LEP."
                    ),
                    original=entry.date_text,
                    proposed=f"{entry.date_text} *",
                    page=entry.page,
                    bbox=entry.bbox,
                )
            )
            continue
        if not declared and entry.starred:
            observed = f"« {status} »" if status else "absente des Highlights"
            findings.append(
                RevisionFinding(
                    control=UNDECLARED_STAR,
                    message=(
                        f"{context} porte une « * » dans la LEP alors qu'elle est "
                        f"{observed} : la page doit être déclarée R ou N, ou la "
                        "« * » doit être retirée."
                    ),
                    original=entry.date_text,
                    proposed=entry.date_text.replace("*", "").rstrip(),
                    page=entry.page,
                    bbox=entry.bbox,
                )
            )
            continue
        if entry.is_blank or status == "D":
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
            findings.append(
                RevisionFinding(
                    control=UNDECLARED_PAGE,
                    message=(
                        f"{context} porte la date de révision {revision.text} dans la "
                        "LEP mais n'est déclarée modifiée ni dans les Highlights "
                        "(R ou N) ni par une « * »."
                    ),
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


def _footer_findings(state: RevisionState) -> list[RevisionFinding]:
    revision = state.revision_date
    assert revision is not None
    lep = state.lep_by_key
    findings: list[RevisionFinding] = []
    for footer in state.footers:
        if page_key_prefix(footer.page_key) == HIGHLIGHTS_KEY_PREFIX:
            continue
        if footer.page_key is None:
            continue
        entry = lep.get(footer.page_key)
        declared = state.is_declared_modified(footer.page_key)

        if entry is None:
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
                        bbox=None,
                    )
                )
            continue

        if state.is_contested(footer.page_key):
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
        findings.append(
            RevisionFinding(
                control=FOOTER_DATE,
                message=(
                    f"Le pied de page de « {footer.label_text} » porte "
                    f"« {footer.date_text or 'aucune date'} » au lieu de {reason}."
                ),
                original=footer.date_text or footer.label_text,
                proposed=expected.text,
                page=footer.page,
                bbox=footer.date_bbox,
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
                    bbox=footer.label_bbox or footer.date_bbox,
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
                    bbox=footer.date_bbox,
                )
            )

    return findings


def _missing_page_findings(state: RevisionState) -> list[RevisionFinding]:
    if not state.full_document:
        return []
    found = {footer.page_key for footer in state.footers}
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
            if expected not in listed and expected not in missing:
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
    findings: list[RevisionFinding] = []
    for entry in state.highlights:
        match = _PAGE_LABEL_RE.match(entry.pages_text)
        if match is None:
            continue
        multiple = len(entry.page_keys) > 1
        # A single page is written « Page » plus two spaces so its number
        # stays aligned with the numbers of the « Pages » rows.
        expected = f"{'Pages' if multiple else 'Page'}{' ' if multiple else '  '}{match.group('rest')}"
        if entry.pages_text == expected:
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


def revision_findings(state: RevisionState) -> list[RevisionFinding]:
    """Cross-check Highlights, LEP and footers, one finding per divergence."""
    if not state.available:
        return []
    findings = (
        _lep_findings(state)
        + _footer_findings(state)
        + _footer_page_number_findings(state)
        + _missing_page_findings(state)
        + _pairing_findings(state)
        + _page_label_findings(state)
    )
    return sorted(findings, key=lambda finding: (finding.page, finding.control))


def findings_for(state: RevisionState, control: str) -> list[RevisionFinding]:
    return [finding for finding in state.findings if finding.control == control]
