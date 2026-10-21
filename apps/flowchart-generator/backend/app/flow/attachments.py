"""Pieces jointes de l'assistant.

Deux familles :
- fichiers structures (Excel/CSV d'etapes, JSON, DSL) -> import direct d'un logigramme ;
- documents (TXT, MD, DOCX, PDF, PPTX, Excel/CSV quelconque) -> texte de reference transmis au LLM.
Un classeur sans colonnes d'etapes reconnues est lu comme document (toutes ses feuilles).
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Literal

from lxml import etree

from app.core.errors import AppError
from app.flow.model import FlowGraph
from app.flow.parsers.json_dsl import parse_json_or_dsl
from app.flow.parsers.table import parse_table

TABLE_EXT = (".xlsx", ".xlsm", ".csv")
GRAPH_TEXT_EXT = (".json", ".dsl", ".flow")
DOC_TEXT_EXT = (".txt", ".md")
DOCX_EXT = (".docx",)
PDF_EXT = (".pdf",)
PPTX_EXT = (".pptx",)
ACCEPTED_EXT = TABLE_EXT + GRAPH_TEXT_EXT + DOC_TEXT_EXT + DOCX_EXT + PDF_EXT + PPTX_EXT

MAX_DOC_CHARS = 50_000
# Erreurs du parseur d'etapes signifiant "ce n'est pas un tableau de logigramme" -> lu comme document.
_NOT_A_FLOW_TABLE = {"TABLE_COLUMNS", "TABLE_EMPTY"}
# Garde-fou anti zip-bomb sur le XML decompresse d'un DOCX.
_MAX_DOCX_XML = 20 * 1024 * 1024
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MAX_PDF_PAGES = 200


@dataclass
class Attachment:
    kind: Literal["graph", "document"]
    name: str
    graph: FlowGraph | None = None
    text: str = ""
    truncated: bool = False
    warnings: list[str] = field(default_factory=list)


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def docx_text(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > _MAX_DOCX_XML:
                raise AppError("FILE_TOO_LARGE", "Document Word trop volumineux", status_code=413)
            xml = archive.read(info)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise AppError("FILE_INVALID", "Document Word illisible", status_code=422) from exc
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    root = etree.fromstring(xml, parser)
    paragraphs = ["".join(t.text or "" for t in p.iter(f"{_W_NS}t")) for p in root.iter(f"{_W_NS}p")]
    return "\n".join(p for p in paragraphs if p.strip())


def pdf_text(content: bytes) -> str:
    import pymupdf

    try:
        doc = pymupdf.open(stream=content, filetype="pdf")
    except Exception as exc:  # PyMuPDF leve des exceptions heterogenes
        raise AppError("FILE_INVALID", "Document PDF illisible", status_code=422) from exc
    pages: list[str] = []
    size = 0
    with doc:
        for index, page in enumerate(doc):
            if index >= _MAX_PDF_PAGES or size > MAX_DOC_CHARS:
                break
            text = page.get_text().strip()
            if text:
                pages.append(f"## Page {index + 1}\n{text}")
                size += len(text)
    return "\n".join(pages)


def pptx_text(content: bytes) -> str:
    from pptx import Presentation

    try:
        prs = Presentation(io.BytesIO(content))
    except Exception as exc:  # python-pptx leve des exceptions heterogenes
        raise AppError("FILE_INVALID", "Presentation PowerPoint illisible", status_code=422) from exc
    slides: list[str] = []
    for index, slide in enumerate(prs.slides, start=1):
        lines = [f"## Diapositive {index}"]
        for shape in slide.shapes:
            if shape.has_text_frame:
                lines.extend(p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip())
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    lines.append(" | ".join(c.text.strip() for c in row.cells if c.text.strip()))
        if len(lines) > 1:
            slides.append("\n".join(lines))
    return "\n".join(slides)


def _cells(row: tuple[object, ...]) -> str:
    return " | ".join(str(c).strip() for c in row if c is not None and str(c).strip())


def workbook_text(content: bytes) -> str:
    """Texte de toutes les feuilles d'un classeur, borne a MAX_DOC_CHARS (+1 pour detecter la troncature)."""
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl leve des exceptions heterogenes
        raise AppError("TABLE_UNREADABLE", "Classeur Excel illisible", status_code=422) from exc
    lines: list[str] = []
    size = 0
    try:
        for ws in wb.worksheets:
            lines.append(f"## Feuille : {ws.title}")
            for row in ws.iter_rows(values_only=True):
                line = _cells(row)
                if line:
                    lines.append(line)
                    size += len(line) + 1
                if size > MAX_DOC_CHARS:
                    return "\n".join(lines)
    finally:
        wb.close()
    return "\n".join(lines)


def _table_as_document(filename: str, content: bytes) -> Attachment:
    if filename.lower().endswith(".csv"):
        return _document(filename, _decode(content))
    return _document(filename, workbook_text(content))


def _document(name: str, text: str) -> Attachment:
    text = text.strip()
    if not text:
        raise AppError("FILE_EMPTY", "Aucun texte exploitable dans le fichier", status_code=422)
    return Attachment(
        kind="document", name=name, text=text[:MAX_DOC_CHARS], truncated=len(text) > MAX_DOC_CHARS
    )


def read_attachment(filename: str, content: bytes) -> Attachment:
    low = filename.lower()
    if not low.endswith(ACCEPTED_EXT):
        raise AppError(
            "FILE_TYPE", "Type de fichier non pris en charge", status_code=415, detail=list(ACCEPTED_EXT)
        )
    if low.endswith(TABLE_EXT):
        try:
            graph, warnings = parse_table(content, filename)
        except AppError as exc:
            if exc.code not in _NOT_A_FLOW_TABLE:
                raise
            return _table_as_document(filename, content)
        return Attachment(kind="graph", name=filename, graph=graph, warnings=warnings)
    if low.endswith(DOCX_EXT):
        return _document(filename, docx_text(content))
    if low.endswith(PDF_EXT):
        return _document(filename, pdf_text(content))
    if low.endswith(PPTX_EXT):
        return _document(filename, pptx_text(content))
    text = _decode(content)
    if low.endswith(GRAPH_TEXT_EXT):
        graph, warnings = parse_json_or_dsl(text)
        return Attachment(kind="graph", name=filename, graph=graph, warnings=warnings)
    return _document(filename, text)


_DSL_NODE = re.compile(r"^\s*[\w.-]+\s+\[[a-z]+\]\s+\S", re.MULTILINE)
_DSL_EDGE = re.compile(r"^\s*[\w.-]+\s*->\s*[\w.-]+", re.MULTILINE)


def looks_structured(text: str) -> bool:
    """JSON FlowGraph ou DSL colle directement dans la conversation."""
    stripped = text.lstrip()
    if stripped.startswith("{"):
        return '"nodes"' in stripped
    return bool(_DSL_NODE.search(text) and _DSL_EDGE.search(text))
