"""Recover the S1000D data-module structure from the published PDF render.

The Doc Reviewer only sees the printed PDF, never the S1000D XML. Data modules
are therefore recognised through their data module code (DMC) and through the
List Of Effective Data Modules (LOEDM) that Thales prints in the front matter.
Every helper returns "unknown" (None / empty) instead of guessing when the
expected structure is not found, so callers can report INCONCLUSIVE.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass

from app.parsers.pdf_parser import ParsedPage, ParsedPdf

# MIC-SDC-SYSTEM-SUBSYSTEM-ASSY-DISASSY-INFO-ITEMLOC, e.g. F9111CMON-A-20-02-00-00A-800A-A.
# The information code is three alphanumeric characters (00T = change record) and a variant letter.
DMC_RE = re.compile(
    r"\b[A-Z0-9]{2,14}-[A-Z0-9]{1,4}-[A-Z0-9]{2,3}-[A-Z0-9]{2}-[A-Z0-9]{2,4}"
    r"-[A-Z0-9]{3,4}-[A-Z0-9]{3}[A-Z]-[A-Z0-9]\b"
)

# Status letters printed in the LOEDM, mapped to the S1000D issue types.
STATUS_CHANGED = "C"
STATUS_NEW = "N"
STATUS_REVISED = "R"
STATUS_STATUS = "S"
STATUS_DELETED = "D"
_STATUS_LETTER_RE = re.compile(r"(?<![\w-])([NCRSD])(?![\w-])")

# Generic data modules are shared between manuals; adapt this marker to the
# convention used in the published LOEDM.
GENERIC_DM_RE = re.compile(r"(?i)\bgeneric\b")

_LOEDM_TITLE_RE = re.compile(r"(?im)^\s*LIST\s+OF\s+EFFECTIVE\s+DATA\s+MODULES\b")
_LOEDM_HEADER_RE = re.compile(r"(?im)^[ \t]*(?:Status|Issue[ \t]+Date)[ \t]*$")
# The renderer wraps a long DMC after its model identification code: "F9111FCTN-\nA-22-15-...".
_DMC_BREAK_RE = re.compile(
    r"(?<=[A-Z0-9]-)[ \t]*\n[ \t]*(?=[A-Z0-9]{1,4}-[A-Z0-9]{2,3}-[A-Z0-9]{2}-)"
)
_END_OF_RE = re.compile(r"(?i)^\s*End\s+of\b")
_IPL_TITLE_RE = re.compile(
    r"(?im)^\s*(?:ILLUSTRATED\s+PARTS\s+(?:LIST|DATA)|DETAILED\s+PARTS\s+LIST)\s*$"
)
_IPL_INFO_CODE_PREFIX = "941"

_MONTHS = {
    name: index
    for index, name in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"),
        start=1,
    )
}
_MONTH_PATTERN = "|".join(_MONTHS)
_DATE_PATTERNS = (
    re.compile(
        r"(?<![\d-])(?P<y>\d{4})-(?P<m>0[1-9]|1[0-2])"
        r"(?:-(?P<d>0[1-9]|[12]\d|3[01]))?(?![\d-])"
    ),
    re.compile(
        rf"(?<!\d)(?P<d>\d{{1,2}})\s+(?P<mon>{_MONTH_PATTERN})[A-Z]*\.?\s+"
        r"(?P<y>\d{4}|\d{2})(?!\d)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?P<mon>{_MONTH_PATTERN})[A-Z]*\.?\s+(?P<d>\d{{1,2}}),\s*(?P<y>\d{{4}})(?!\d)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?P<mon>{_MONTH_PATTERN})[A-Z]*\.?\s+(?:(?P<d>\d{{1,2}})\s*/\s*)?"
        r"(?P<y>\d{4}|\d{2})(?!\d)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![\d/])(?:(?P<d>\d{1,2})/)?(?P<m>\d{1,2})/(?P<y>\d{4})(?![\d/])"
    ),
)


@dataclass(frozen=True)
class IssueDate:
    year: int
    month: int
    day: int | None = None

    def __str__(self) -> str:
        suffix = f"-{self.day:02d}" if self.day is not None else ""
        return f"{self.year}-{self.month:02d}{suffix}"


def _full_year(value: str) -> int:
    year = int(value)
    if len(value) == 4:
        return year
    return 2000 + year if year < 50 else 1900 + year


def find_issue_date(text: str) -> tuple[IssueDate, str] | None:
    """Return the first date written in one of the supported layouts and its raw text."""
    best: tuple[int, IssueDate, str] | None = None
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if match is None or (best is not None and match.start() >= best[0]):
            continue
        groups = match.groupdict()
        month = (
            _MONTHS[groups["mon"][:3].upper()]
            if groups.get("mon")
            else int(groups["m"])
        )
        if not 1 <= month <= 12:
            continue
        day = int(groups["d"]) if groups.get("d") else None
        if day is not None and not 1 <= day <= 31:
            continue
        best = (match.start(), IssueDate(_full_year(groups["y"]), month, day), match.group(0))
    return (best[1], best[2]) if best is not None else None


def parse_issue_date(text: str | None) -> IssueDate | None:
    found = find_issue_date(text or "")
    return found[0] if found is not None else None


def same_issue_date(left: IssueDate, right: IssueDate) -> bool:
    """Compare year and month, plus the day when both dates carry one."""
    return (
        left.year == right.year
        and left.month == right.month
        and (left.day is None or right.day is None or left.day == right.day)
    )


@dataclass(frozen=True)
class PageText:
    """All page texts of a document joined, with the offset of each page."""

    pages: tuple[ParsedPage, ...]
    text: str
    starts: tuple[int, ...]

    @classmethod
    def build(cls, pages: Sequence[ParsedPage]) -> PageText:
        starts: list[int] = []
        offset = 0
        for page in pages:
            starts.append(offset)
            offset += len(page.text) + 1
        return cls(tuple(pages), "\n".join(page.text for page in pages), tuple(starts))

    def locate(self, offset: int) -> tuple[ParsedPage, int]:
        """Return the page holding `offset` and the offset inside that page text."""
        index = max(bisect_right(self.starts, offset) - 1, 0)
        page = self.pages[index]
        return page, min(max(offset - self.starts[index], 0), len(page.text))


def complete_pages(parsed_pdf: ParsedPdf) -> list[ParsedPage]:
    """Every page of the document, even when the analysis covers a page subset."""
    return list(parsed_pdf.full_document_pages or parsed_pdf.pages)


@dataclass(frozen=True)
class LoedmRow:
    dmc: str
    page: int
    text: str
    issue_date: IssueDate | None
    issue_date_text: str | None
    status: str | None
    title: str = ""

    @property
    def info_code(self) -> str:
        return self.dmc.split("-")[-2]

    @property
    def generic(self) -> bool:
        # Generic DMs carry a "Generic - ..." title and a model identification code ending in GENE.
        return bool(GENERIC_DM_RE.search(self.title)) or self.dmc.split("-")[0].endswith("GENE")

    @property
    def modified(self) -> bool:
        return self.status in {STATUS_CHANGED, STATUS_NEW, STATUS_REVISED, STATUS_STATUS}


def unwrap_dmc(text: str) -> str:
    """Rejoin the DMCs that the renderer wrapped onto two lines."""
    return _DMC_BREAK_RE.sub("", text)


def loedm_page_numbers(pages: Sequence[ParsedPage]) -> list[int]:
    """Pages of the LOEDM: a titled page holding DMCs plus its dense continuations."""
    numbers: list[int] = []
    for page in pages:
        dmc_count = len(DMC_RE.findall(unwrap_dmc(page.text)))
        titled = bool(_LOEDM_TITLE_RE.search(page.text))
        if not numbers:
            if titled and dmc_count:
                numbers.append(page.page)
            continue
        if (titled and dmc_count) or dmc_count >= 5:
            numbers.append(page.page)
        else:
            break
    return numbers


def _row_status(chunk: str, date_end: int | None) -> str | None:
    letters = [(match.start(), match.group(1)) for match in _STATUS_LETTER_RE.finditer(chunk)]
    if not letters:
        return None
    if date_end is not None:
        after = [letter for start, letter in letters if start >= date_end]
        if after:
            return after[0]
    return letters[0][1]


def is_s1000d_document(pages: Sequence[ParsedPage]) -> bool:
    """An S1000D publication prints a LOEDM that lists data module codes."""
    return bool(loedm_page_numbers(pages))


def _title_first_layout(texts: Sequence[tuple[int, str]]) -> bool:
    """Thales prints the title before the DMC; a title right after the date is the older layout."""
    for _number, text in texts:
        first = DMC_RE.search(text)
        if first is None:
            continue
        header = None
        for header in _LOEDM_HEADER_RE.finditer(text, 0, first.start()):
            pass
        title = _LOEDM_TITLE_RE.search(text)
        start = (
            header.end()
            if header is not None
            else title.end() if title is not None and title.end() < first.start() else 0
        )
        return bool(re.search(r"[A-Za-z]{3}", text[start : first.start()]))
    return False


_STATUS_LINE_RE = re.compile(r"[ \t]*(?:\n[ \t]*)?([NCRSD])[ \t]*(?:\n|$)")


def _title_first_rows(number: int, text: str) -> list[LoedmRow]:
    matches = list(DMC_RE.finditer(text))
    header = None
    for header in _LOEDM_HEADER_RE.finditer(text, 0, matches[0].start() if matches else 0):
        pass
    cursor = header.end() if header is not None else 0
    rows: list[LoedmRow] = []
    for index, match in enumerate(matches):
        limit = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        tail = text[match.end() : limit]
        head = "\n".join(tail.splitlines()[:6])
        found = find_issue_date(head)
        status = None
        row_end = match.end()
        if found is not None:
            date_end = head.find(found[1]) + len(found[1])
            status_match = _STATUS_LINE_RE.match(tail, date_end)
            status = status_match.group(1) if status_match is not None else None
            row_end = match.end() + (status_match.end() if status_match is not None else date_end)
        title = " ".join(text[cursor : match.start()].split())
        rows.append(
            LoedmRow(
                dmc=match.group(0),
                page=number,
                text=f"{title} {match.group(0)} {' '.join(head.split())}",
                issue_date=found[0] if found is not None else None,
                issue_date_text=found[1] if found is not None else None,
                status=status,
                title=title,
            )
        )
        cursor = max(row_end, cursor)
    return rows


def _title_last_rows(number: int, text: str) -> list[LoedmRow]:
    matches = list(DMC_RE.finditer(text))
    rows: list[LoedmRow] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunk = " ".join(" ".join(text[match.end() : end].splitlines()[:6]).split())
        found = find_issue_date(chunk)
        date_end = None
        if found is not None:
            date_end = chunk.find(found[1]) + len(found[1])
        rows.append(
            LoedmRow(
                dmc=match.group(0),
                page=number,
                text=f"{match.group(0)} {chunk}",
                issue_date=found[0] if found is not None else None,
                issue_date_text=found[1] if found is not None else None,
                status=_row_status(chunk, date_end),
                title=chunk[date_end:].strip() if date_end is not None else chunk,
            )
        )
    return rows


def parse_loedm(pages: Sequence[ParsedPage]) -> tuple[list[LoedmRow], list[int]]:
    """Parse the LOEDM rows; an empty row list means the table was not recognised."""
    page_numbers = loedm_page_numbers(pages)
    by_number = {page.page: page for page in pages}
    texts = [(number, unwrap_dmc(by_number[number].text)) for number in page_numbers]
    parse_page = _title_first_rows if _title_first_layout(texts) else _title_last_rows
    rows: list[LoedmRow] = []
    for number, text in texts:
        rows.extend(parse_page(number, text))
    return rows, page_numbers


def _edge_text(page: ParsedPage) -> str:
    """Header and footer text, where Thales prints the DMC of the current module."""
    if page.lines and page.page_height > 0:
        top, bottom = page.page_height * 0.12, page.page_height * 0.88
        return "\n".join(
            line.text for line in page.lines if line.bbox[1] < top or line.bbox[3] > bottom
        )
    lines = [line for line in page.text.splitlines() if line.strip()]
    return "\n".join(lines[:4] + lines[-4:])


def _dm_markers(page: ParsedPage) -> tuple[list[tuple[str, bool]], bool]:
    """DMC lines marking a data module (start near the top of its page, end before "End of").

    The flag tells that the page also lists DMCs elsewhere (Highlights...): such a page is a table.
    """
    source = [line.text for line in page.lines] if page.lines else page.text.splitlines()
    lines = [line.strip() for line in source if line.strip()]
    markers: list[tuple[str, bool]] = []
    listing = False
    for index, line in enumerate(lines):
        if not DMC_RE.fullmatch(line):
            continue
        following = lines[index + 1] if index + 1 < len(lines) else ""
        is_end = _END_OF_RE.match(following) is not None
        if is_end or index < _START_MARKER_LINES:
            markers.append((line, is_end))
        else:
            listing = True
    return markers, listing


_START_MARKER_LINES = 6
# A page with many DMC markers (LOEDM-like table) is not the boundary of a data module.
_MAX_MARKERS_PER_PAGE = 3


def dm_page_map(
    pages: Sequence[ParsedPage],
    rows: Sequence[LoedmRow],
    loedm_pages: Sequence[int],
) -> dict[int, str]:
    """Map each page to its data module: DMC start/end markers, else the header/footer DMC."""
    known = {row.dmc for row in rows}
    skipped = set(loedm_pages)
    mapping: dict[int, str] = {}
    current: str | None = None
    for page in pages:
        if page.page in skipped:
            current = None
            continue
        markers, listing = _dm_markers(page)
        if len(markers) > _MAX_MARKERS_PER_PAGE or (listing and not markers):
            current = None
            continue
        if markers:
            mapping[page.page] = markers[0][0]
            for code, is_end in markers:
                current = None if is_end else code
            continue
        found = DMC_RE.findall(_edge_text(page))
        if found:
            current = next((code for code in found if code in known), found[0])
        if current is not None:
            mapping[page.page] = current
    return mapping


def ipl_page_numbers(
    pages: Sequence[ParsedPage],
    rows: Sequence[LoedmRow],
    page_map: dict[int, str],
) -> list[int]:
    """Pages of the illustrated parts list (IPL data modules, else from its title page to the end)."""
    ipl_codes = {row.dmc for row in rows if row.info_code.startswith(_IPL_INFO_CODE_PREFIX)}
    by_dm = [page.page for page in pages if page_map.get(page.page) in ipl_codes]
    if by_dm:
        return by_dm
    skipped = set(loedm_page_numbers(pages))
    start = next(
        (
            page.page
            for page in pages
            if page.page not in skipped and _IPL_TITLE_RE.search(page.text)
        ),
        None,
    )
    return [page.page for page in pages if start is not None and page.page >= start]


@dataclass(frozen=True)
class RevisionBar:
    x: float
    top: float
    bottom: float


def _is_black(color: tuple[float, ...] | None) -> bool:
    return color is not None and len(color) >= 3 and all(value <= 0.05 for value in color[:3])


def _filled_bars(page: ParsedPage) -> list[tuple[float, float, float]]:
    """Bars exported as a black-filled rectangle split into four lines: (x center, top, bottom)."""
    sides: dict[tuple[float, float], set[float]] = {}
    for primitive in page.vector_primitives:
        x0, y0, x1, y1 = primitive.bbox
        if (
            primitive.kind == "line"
            and primitive.color is None
            and _is_black(primitive.fill)
            and abs(x1 - x0) < 0.5
            and abs(y1 - y0) >= 8.0
        ):
            sides.setdefault((round(min(y0, y1), 0), round(max(y0, y1), 0)), set()).add(round(x0, 1))
    bars: list[tuple[float, float, float]] = []
    for (top, bottom), positions in sides.items():
        ordered = sorted(positions)
        for left_side, right_side in zip(ordered, ordered[1:]):
            # A thin gap is a double table border, a bar is a few points wide.
            if 1.0 <= right_side - left_side <= 6.0:
                bars.append(((left_side + right_side) / 2, top, bottom))
    return bars


def revision_bars(page: ParsedPage) -> list[RevisionBar]:
    """Black vertical bars drawn in the outer margins, left or right of the body text."""
    if not page.vector_primitives:
        return []
    page_width = page.page_width or max((span.bbox[2] for span in page.spans), default=0.0)
    height = page.page_height
    body = [
        span
        for span in page.spans
        if height <= 0 or height * 0.12 < (span.bbox[1] + span.bbox[3]) / 2 < height * 0.88
    ] or page.spans
    left = min((span.bbox[0] for span in body), default=None)
    right = max((span.bbox[2] for span in body), default=None)

    def in_outer_margin(center: float) -> bool:
        if left is not None and right is not None:
            return center < left - 1.0 or center > right + 1.0
        return page_width > 0 and (center <= page_width * 0.25 or center >= page_width * 0.75)

    bars: list[RevisionBar] = []
    for center, top, bottom in _filled_bars(page):
        if in_outer_margin(center):
            bars.append(RevisionBar(x=center, top=top, bottom=bottom))
    for primitive in page.vector_primitives:
        x0, y0, x1, y1 = primitive.bbox
        if primitive.kind == "line" and _is_black(primitive.color):
            if abs(x1 - x0) > max(2.0, primitive.width * 1.5) or not 1.0 <= primitive.width <= 4.5:
                continue
        elif primitive.kind == "rect" and _is_black(primitive.fill):
            if not 1.0 <= abs(x1 - x0) <= 6.0:
                continue
        else:
            continue
        if abs(y1 - y0) < 8.0:
            continue
        center = (x0 + x1) / 2
        if in_outer_margin(center):
            bars.append(RevisionBar(x=center, top=min(y0, y1), bottom=max(y0, y1)))
    return bars
