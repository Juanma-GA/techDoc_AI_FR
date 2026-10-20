"""Routes /api/v1/parse/* et /api/v1/render/* : conversion sans persistance.

parse  : texte libre (IA + repli), tableau Excel/CSV, JSON ou DSL -> FlowGraph.
render : FlowGraph -> apercu SVG ou fichier dans l'un des formats d'export.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.flow.exporters import EXPORTERS
from app.flow.model import FlowGraph
from app.flow.parsers.json_dsl import parse_json_or_dsl
from app.flow.parsers.table import parse_table
from app.flow.parsers.text_llm import parse_text
from app.schemas import ParseJsonIn, ParseResultOut, ParseTextIn

router = APIRouter(tags=["convert"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_TABLE_EXT = (".xlsx", ".xlsm", ".csv")


class FormatOut(BaseModel):
    format: str
    extension: str
    media_type: str


def safe_filename(name: str, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")[:80] or "logigramme"
    return f"{base}.{ext}"


def export_response(graph: FlowGraph, fmt: str, name: str) -> Response:
    if fmt not in EXPORTERS:
        raise AppError("FORMAT_UNKNOWN", f"Format inconnu : {fmt}", status_code=404, detail=sorted(EXPORTERS))
    renderer, media_type, ext = EXPORTERS[fmt]
    content = renderer(graph)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename(name, ext)}"'},
    )


@router.get("/formats", response_model=list[FormatOut])
def list_formats() -> list[FormatOut]:
    return [FormatOut(format=k, extension=ext, media_type=mt) for k, (_, mt, ext) in EXPORTERS.items()]


@router.post("/parse/text", response_model=ParseResultOut)
async def parse_text_route(body: ParseTextIn, db: Session = Depends(get_db)) -> ParseResultOut:
    graph, warnings, llm_used = await parse_text(db, body.text)
    return ParseResultOut(graph=graph, warnings=warnings, llm_used=llm_used)


@router.post("/parse/json", response_model=ParseResultOut)
def parse_json_route(body: ParseJsonIn) -> ParseResultOut:
    graph, warnings = parse_json_or_dsl(body.content)
    return ParseResultOut(graph=graph, warnings=warnings)


@router.post("/parse/table", response_model=ParseResultOut)
async def parse_table_route(file: UploadFile = File(...)) -> ParseResultOut:
    filename = file.filename or ""
    if not filename.lower().endswith(_TABLE_EXT):
        raise AppError("FILE_TYPE", "Fichier attendu : .xlsx, .xlsm ou .csv", status_code=415)
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise AppError("FILE_TOO_LARGE", "Fichier trop volumineux (5 Mo max)", status_code=413)
    graph, warnings = parse_table(content, filename)
    return ParseResultOut(graph=graph, warnings=warnings)


@router.post("/render/preview")
def render_preview(graph: FlowGraph) -> Response:
    renderer, media_type, _ = EXPORTERS["svg"]
    return Response(content=renderer(graph), media_type=media_type)


@router.post("/render/{fmt}")
def render_export(fmt: str, graph: FlowGraph) -> Response:
    return export_response(graph, fmt, graph.title)
