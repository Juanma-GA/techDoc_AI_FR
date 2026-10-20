"""Registre des formats d'export : format -> (rendu, media type, extension)."""

from __future__ import annotations

from collections.abc import Callable

from app.flow.exporters.bpmn import render_bpmn
from app.flow.exporters.drawio import render_drawio
from app.flow.exporters.excel import render_xlsx
from app.flow.exporters.mermaid import render_mermaid
from app.flow.exporters.powerpoint import render_pptx
from app.flow.exporters.s1000d import render_s1000d
from app.flow.exporters.svg import render_svg
from app.flow.model import FlowGraph


def render_json(graph: FlowGraph) -> str:
    return graph.model_dump_json(indent=2)


Renderer = Callable[[FlowGraph], str | bytes]

EXPORTERS: dict[str, tuple[Renderer, str, str]] = {
    "mermaid": (render_mermaid, "text/plain; charset=utf-8", "mmd"),
    "svg": (render_svg, "image/svg+xml", "svg"),
    "drawio": (render_drawio, "application/xml", "drawio"),
    "bpmn": (render_bpmn, "application/xml", "bpmn"),
    "pptx": (
        render_pptx,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pptx",
    ),
    "xlsx": (render_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "json": (render_json, "application/json", "json"),
    "s1000d": (render_s1000d, "application/xml", "xml"),
}

__all__ = ["EXPORTERS", "render_json"]
