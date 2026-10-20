"""Routes /api/v1/flows : CRUD des logigrammes sauvegardes + export."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.convert import export_response
from app.core.errors import AppError
from app.db.models import Flow
from app.db.session import get_db
from app.flow.model import FlowGraph
from app.schemas import FlowCreate, FlowOut, FlowSummary, FlowUpdate

router = APIRouter(prefix="/flows", tags=["flows"])


def _graph(flow: Flow) -> FlowGraph:
    return FlowGraph.model_validate_json(flow.graph_json)


def _summary(flow: Flow, graph: FlowGraph) -> FlowSummary:
    return FlowSummary(
        id=flow.id,
        name=flow.name,
        source_type=flow.source_type,
        node_count=len(graph.nodes),
        edge_count=len(graph.edges),
        created_at=flow.created_at,
        updated_at=flow.updated_at,
    )


def _out(flow: Flow) -> FlowOut:
    graph = _graph(flow)
    return FlowOut(**_summary(flow, graph).model_dump(), source_text=flow.source_text, graph=graph)


def _get(db: Session, flow_id: uuid.UUID) -> Flow:
    flow = db.get(Flow, str(flow_id))
    if flow is None:
        raise AppError(
            "FLOW_NOT_FOUND", "Logigramme introuvable", status_code=404, detail={"id": str(flow_id)}
        )
    return flow


@router.get("", response_model=list[FlowSummary])
def list_flows(db: Session = Depends(get_db)) -> list[FlowSummary]:
    flows = db.scalars(select(Flow).order_by(Flow.updated_at.desc())).all()
    return [_summary(f, _graph(f)) for f in flows]


@router.post("", response_model=FlowOut, status_code=201)
def create_flow(body: FlowCreate, db: Session = Depends(get_db)) -> FlowOut:
    flow = Flow(
        id=str(uuid.uuid4()),
        name=body.name,
        source_type=body.source_type,
        source_text=body.source_text,
        graph_json=body.graph.model_dump_json(),
    )
    db.add(flow)
    db.commit()
    db.refresh(flow)
    return _out(flow)


@router.get("/{flow_id}", response_model=FlowOut)
def get_flow(flow_id: uuid.UUID, db: Session = Depends(get_db)) -> FlowOut:
    return _out(_get(db, flow_id))


@router.put("/{flow_id}", response_model=FlowOut)
def update_flow(flow_id: uuid.UUID, body: FlowUpdate, db: Session = Depends(get_db)) -> FlowOut:
    flow = _get(db, flow_id)
    if body.name is not None:
        flow.name = body.name
    if body.source_type is not None:
        flow.source_type = body.source_type
    if body.source_text is not None:
        flow.source_text = body.source_text
    if body.graph is not None:
        flow.graph_json = body.graph.model_dump_json()
    db.commit()
    db.refresh(flow)
    return _out(flow)


@router.delete("/{flow_id}", status_code=204)
def delete_flow(flow_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    db.delete(_get(db, flow_id))
    db.commit()
    return Response(status_code=204)


@router.get("/{flow_id}/export/{fmt}")
def export_flow(flow_id: uuid.UUID, fmt: str, db: Session = Depends(get_db)) -> Response:
    flow = _get(db, flow_id)
    return export_response(_graph(flow), fmt, flow.name)
