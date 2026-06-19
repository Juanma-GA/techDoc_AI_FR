"""Tests parser docx : reconnaissance de zones, alignement, lecture des revisions."""

from __future__ import annotations

import io

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.core.docx_zones import recognize_zones
from app.parsers.docx_parser import parse_docx


def _save(d) -> str:
    import tempfile

    path = tempfile.mktemp(suffix=".docx")
    d.save(path)
    return path


def test_zone_recognition_and_footer():
    d = Document()
    d.add_heading("HIGHLIGHTS", level=1)
    d.add_paragraph("Revision row content.")
    d.add_heading("GENERAL", level=1)
    d.add_paragraph("Body content here.")
    d.sections[0].footer.paragraphs[0].text = "ATA 32 Page 1 2024"
    parsed = recognize_zones(parse_docx(_save(d)))
    sem = {b.text[:20]: b.semantic_zone for b in parsed.blocks if b.text.strip()}
    assert sem["HIGHLIGHTS"] == "highlights_table"
    assert sem["Body content here."] == "body"
    assert any(b.zone == "footer" for b in parsed.blocks)
    assert parsed.footers and "ATA" in parsed.footers[0]


def test_alignment_detected():
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    d = Document()
    p = d.add_paragraph("Justified text.")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    parsed = parse_docx(_save(d))
    assert any(b.alignment == "justify" for b in parsed.blocks)


def test_tracked_change_insertion_detected():
    d = Document()
    para = d.add_paragraph("Inserted content.")
    p = para._p
    ins = OxmlElement("w:ins")
    ins.set(qn("w:author"), "Reviewer")
    for r in list(p.findall(qn("w:r"))):
        p.remove(r)
        ins.append(r)
    p.append(ins)
    parsed = parse_docx(_save(d))
    revised = [b for b in parsed.blocks if b.revised]
    assert revised and revised[0].revision_kind == "ins"
    assert parsed.revisions and parsed.revisions[0].author == "Reviewer"
