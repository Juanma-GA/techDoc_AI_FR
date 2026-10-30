"""Assign stable, DM-local identifiers to generated S1000D content."""

from lxml import etree

_ID_PREFIXES = (
    ("proceduralStep", "stp"),
    ("levelledPara", "par"),
    ("figure", "fig"),
    ("table", "tab"),
    ("supportEquipDescr", "seq"),
    ("supplyDescr", "sup"),
    ("spareDescr", "spa"),
)


def normalize_dm_ids(root: etree._Element) -> None:
    for tag, prefix in _ID_PREFIXES:
        for number, element in enumerate(root.iter(tag), start=1):
            element.set("id", f"{prefix}-{number:04d}")
