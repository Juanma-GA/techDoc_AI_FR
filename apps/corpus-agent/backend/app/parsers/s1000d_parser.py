"""S1000D / XML parser via lxml. Ported from legacy."""

from __future__ import annotations

import re
from typing import Any

from lxml import etree


DMC_REGEX = re.compile(r"DMC[A-Z0-9\-]{3,}")


def parse_s1000d(path: str) -> dict[str, Any]:
    try:
        tree = etree.parse(path)
    except etree.XMLSyntaxError:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        return {
            "text": text,
            "images": [],
            "sections": [],
            "dmc_codes": sorted(set(DMC_REGEX.findall(text))),
        }

    root = tree.getroot()
    text = " ".join(t.strip() for t in root.itertext() if t and t.strip())

    sections: list[str] = []
    for tag in ("dmTitle", "techName", "infoName", "title"):
        for el in root.iter():
            if etree.QName(el).localname == tag:
                t = " ".join(e.strip() for e in el.itertext() if e.strip())
                if t:
                    sections.append(t)

    dmc_codes: set[str] = set(DMC_REGEX.findall(text))
    for el in root.iter():
        tag = etree.QName(el).localname
        if tag in ("dmCode", "dmIdent"):
            parts: list[str] = []
            for attr in (
                "modelIdentCode", "systemDiffCode", "systemCode", "subSystemCode",
                "subSubSystemCode", "assyCode", "disassyCode", "disassyCodeVariant",
                "infoCode", "infoCodeVariant", "itemLocationCode",
            ):
                v = el.get(attr)
                if v:
                    parts.append(v)
            if parts:
                dmc_codes.add("DMC" + "-".join(parts))

    return {
        "text": text,
        "images": [],
        "sections": list(dict.fromkeys(sections)),
        "dmc_codes": sorted(dmc_codes),
    }
