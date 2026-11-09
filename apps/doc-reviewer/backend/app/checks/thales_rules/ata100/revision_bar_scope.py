from __future__ import annotations

import re

from app.parsers.pdf_parser import ParsedPage

_EXEMPT_TITLES = re.compile(
    r"(?im)^\s*(?:"
    r"VENDOR\s+CODE\s+LIST|VCL|"
    r"EQUIPMENT\s+DESIGNATOR\s+INDEX|EDI|"
    r"NUMERICAL\s+INDEX|NI|"
    r"PARTS\s+LIST|PL|"
    r"GEO(?:GRAPHIC(?:AL)?\s+)?\s*LOC(?:ATION)?|"
    r"GEOGRAPHIC(?:AL)?\s+LOCATION|"
    r"OPTIONAL\s+PARTS\s+LIST|OPL"
    r")\s*$"
)
_EXEMPT_PAGE_KEY_PREFIXES = {
    "vcl",
    "vendor code list",
    "edi",
    "equipment designator index",
    "ni",
    "numerical index",
    "pl",
    "parts list",
    "geo loc",
    "geoloc",
    "geographic location",
    "geographical location",
    "opl",
    "optional parts list",
}


def is_revision_bar_exempt_page(page: ParsedPage, page_key: str | None) -> bool:
    page_type = (page.page_type or "").replace("_", " ")
    if _EXEMPT_TITLES.search(page_type):
        return True
    if _EXEMPT_TITLES.search(page.text or ""):
        return True
    if not page_key:
        return False
    prefix, _, _number = page_key.rpartition(" ")
    normalized_prefix = " ".join(prefix.casefold().replace("_", " ").split())
    return normalized_prefix in _EXEMPT_PAGE_KEY_PREFIXES
