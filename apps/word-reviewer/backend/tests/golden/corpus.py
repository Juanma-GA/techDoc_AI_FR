"""Corpus de reference synthetique pour mesurer precision / rappel.

Chaque entree = un .docx synthetique (jamais de donnee client) + l'ensemble des
`rule_code` ATA100 deterministes attendus. Sert au harnais de non-regression :
si une regle cesse de se declencher (rappel baisse) ou sur-declenche sur un doc
propre (precision baisse), le test echoue.
"""

from __future__ import annotations

import io
import tempfile
from dataclasses import dataclass, field

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH


@dataclass
class GoldenDoc:
    name: str
    path: str
    expected: set[str] = field(default_factory=set)


def _write(doc: Document) -> str:
    buf = io.BytesIO()
    doc.save(buf)
    path = tempfile.mktemp(suffix=".docx")
    with open(path, "wb") as f:
        f.write(buf.getvalue())
    return path


def _clean_doc() -> GoldenDoc:
    d = Document()
    d.add_heading("GENERAL", level=1)
    p = d.add_paragraph("This maintenance task removes the actuator unit safely.")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    d.sections[0].footer.paragraphs[0].text = "ACME Page 1 2024"
    return GoldenDoc(name="clean", path=_write(d), expected=set())


def _issues_doc() -> GoldenDoc:
    d = Document()
    d.add_heading("GENERAL", level=1)
    d.add_paragraph("Chapter 250 contains several parts to inspect.")
    d.sections[0].footer.paragraphs[0].text = "ACME Page 1 2024"
    expected = {"ATA_CHAPTER_RANGE", "ATA_NO_AMBIGUOUS_QUANT"}
    return GoldenDoc(name="issues", path=_write(d), expected=expected)


def build_corpus() -> list[GoldenDoc]:
    return [_clean_doc(), _issues_doc()]
