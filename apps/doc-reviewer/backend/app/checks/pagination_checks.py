"""Document-wide recto-verso checks for chapter pagination."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.checks.raw import RawSuggestion
from app.parsers.pdf_parser import ParsedPage, ParsedPdf


_CHAPTER_MARKER_RE = re.compile(
    r"^\s*(?:chapter|chapitre)\s+(?:\d+(?:\.\d+)*|[ivxlcdm]+|[a-z])"
    r"(?:\s*[:.-]\s*(?P<title>.*)|\s+(?P<plain_title>.*))?\s*$",
    re.IGNORECASE,
)
_NUMBERED_HEADING_RE = re.compile(r"^\s*(?P<number>\d{1,2})\.\s+(?P<title>.+?)\s*$")
_CONTENTS_PAGE_RE = re.compile(
    r"\b(?:table\s+of\s+contents|contents|sommaire|table\s+des\s+mati[eè]res)\b",
    re.IGNORECASE,
)
_TITLE_CONNECTORS = frozenset(
    {"a", "and", "de", "des", "du", "en", "et", "for", "la", "le", "les", "of", "the"}
)


@dataclass(frozen=True)
class _ChapterStart:
    page: int
    title: str
    span: tuple[int, int]
    bbox: tuple[float, float, float, float] | None = None


def _complete_document_pages(parsed: ParsedPdf) -> list[ParsedPage]:
    pages = parsed.full_document_pages if parsed.full_document_pages is not None else parsed.pages
    if len(pages) != parsed.page_count:
        return []
    if any(page.page != page_number for page_number, page in enumerate(pages, start=1)):
        return []
    return pages


def _chapter_heading(text: str) -> str | None:
    heading = text.strip()
    if not heading:
        return None
    marker = _CHAPTER_MARKER_RE.match(heading)
    if marker is not None:
        marker_title = (marker.group("title") or marker.group("plain_title") or "").strip()
        if not marker_title or _is_heading_title(marker_title):
            return heading

    match = _NUMBERED_HEADING_RE.match(heading)
    if match is None:
        return None
    title = match.group("title").strip()
    return heading if _is_heading_title(title) else None


def _is_heading_title(title: str) -> bool:
    if not title or title[-1] in ".!?;:":
        return False
    words = re.findall(r"[^\W_]+", title)
    letters = [character for character in title if character.isalpha()]
    if not words or not letters:
        return False
    all_upper = all(character.isupper() for character in letters)
    title_case = all(
        word[0].isupper() or word.casefold() in _TITLE_CONNECTORS for word in words
    )
    short_sentence_case = len(words) <= 3 and words[0][0].isupper()
    return all_upper or title_case or short_sentence_case


def _top_lines(page: ParsedPage) -> list[tuple[str, tuple[float, float, float, float] | None]]:
    if not page.lines:
        return [(line, None) for line in (page.text or "").splitlines()]

    lines = sorted(page.lines, key=lambda line: (line.bbox[1], line.bbox[0]))
    if page.page_height > 0:
        lines = [line for line in lines if line.bbox[1] <= page.page_height * 0.3]
    return [(line.text, line.bbox) for line in lines]


def _span(page: ParsedPage, text: str) -> tuple[int, int]:
    start = (page.text or "").find(text)
    return (start, start + len(text)) if start >= 0 else (0, 0)


def _chapter_starts(parsed: ParsedPdf, pages: list[ParsedPage]) -> list[_ChapterStart]:
    pages_by_number = {page.page: page for page in pages}
    starts: dict[int, _ChapterStart] = {}

    for bookmark in parsed.bookmarks:
        page = pages_by_number.get(bookmark.page)
        title = _chapter_heading(bookmark.title)
        if page is None or title is None or _CONTENTS_PAGE_RE.search(page.text or ""):
            continue
        starts[page.page] = _ChapterStart(
            page=page.page,
            title=title,
            span=_span(page, title),
        )

    for page in pages:
        if _CONTENTS_PAGE_RE.search(page.text or ""):
            continue
        for line_text, bbox in _top_lines(page):
            title = _chapter_heading(line_text)
            if title is None:
                continue
            starts.setdefault(
                page.page,
                _ChapterStart(
                    page=page.page,
                    title=title,
                    span=_span(page, line_text.strip()),
                    bbox=bbox,
                ),
            )
            break

    return [starts[page] for page in sorted(starts)]


def _finding(
    *,
    page: int,
    message: str,
    original: str = "",
    span: tuple[int, int] = (0, 0),
    bbox: tuple[float, float, float, float] | None = None,
) -> RawSuggestion:
    return RawSuggestion(
        rule_kind="layout",
        rule_code="LAYOUT_CHAPTER_PARITY",
        severity="warning",
        message=message,
        original=original,
        proposed="",
        page=page,
        span=span,
        bbox=bbox,
    )


def run(parsed: ParsedPdf) -> list[RawSuggestion]:
    """Check chapter boundaries against physical PDF page parity.

    Empty and explicitly labelled blank pages stay in the page sequence, so
    they count toward the even/odd position just like pages with body text.
    """
    pages = _complete_document_pages(parsed)
    if not pages:
        return []

    chapters = _chapter_starts(parsed, pages)
    if not chapters:
        return []

    findings: list[RawSuggestion] = []
    for index, chapter in enumerate(chapters):
        if chapter.page % 2:
            continue
        if index == 0:
            message = (
                f"Le chapitre « {chapter.title} » commence à la page PDF {chapter.page} "
                "(paire) ; un chapitre doit commencer sur une page impaire."
            )
        else:
            previous = chapters[index - 1]
            message = (
                f"Le chapitre « {previous.title} » se termine à la page PDF "
                f"{chapter.page - 1} (impaire) avant « {chapter.title} ». "
                "Vérifier la page paire blanche d'équilibrage pour faire commencer "
                "le chapitre suivant sur une page impaire."
            )
        findings.append(
            _finding(
                page=chapter.page,
                message=message,
                original=chapter.title,
                span=chapter.span,
                bbox=chapter.bbox,
            )
        )

    final_page = pages[-1].page
    if final_page % 2:
        chapter = chapters[-1]
        findings.append(
            _finding(
                page=final_page,
                message=(
                    f"Le dernier chapitre « {chapter.title} » se termine à la page PDF "
                    f"{final_page} (impaire) ; une page paire de fin est attendue, "
                    "blanche si nécessaire."
                ),
            )
        )
    return findings