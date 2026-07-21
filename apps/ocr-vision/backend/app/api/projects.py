"""Routes projets + tables de projet + lignes.

- /projects            : unites de capitalisation
- /project-tables      : instance d'un template dans un projet (porte les lignes)
- /project-tables/{id}/rows, /rows/{id} : lignes extraites
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import ExtractedRow, Project, ProjectTable, TableTemplate
from app.db.session import get_db
from app.schemas import (
    ProjectIn,
    ProjectOut,
    ProjectTableIn,
    ProjectTableOut,
    RowOut,
)

router = APIRouter(tags=["projects"])


# ----- Projets --------------------------------------------------------------


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    rows = db.scalars(select(Project).order_by(Project.created_at.desc())).all()
    return [ProjectOut(id=p.id, name=p.name, created_at=p.created_at) for p in rows]


@router.post("/projects", response_model=ProjectOut)
def create_project(payload: ProjectIn, db: Session = Depends(get_db)) -> ProjectOut:
    p = Project(name=payload.name.strip())
    db.add(p)
    db.commit()
    db.refresh(p)
    return ProjectOut(id=p.id, name=p.name, created_at=p.created_at)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> None:
    p = db.get(Project, project_id)
    if p is None:
        raise AppError("PROJECT_NOT_FOUND", "Projet introuvable.", status_code=404)
    # Cascade applicative (ondelete=CASCADE non garanti sans PRAGMA cote SQLite).
    tables = db.scalars(select(ProjectTable).where(ProjectTable.project_id == project_id)).all()
    for tbl in tables:
        db.query(ExtractedRow).filter(ExtractedRow.project_table_id == tbl.id).delete()
        db.delete(tbl)
    db.delete(p)
    db.commit()


# ----- Tables de projet (instances de template) -----------------------------


def _row_count(db: Session, project_table_id: str) -> int:
    return int(
        db.scalar(
            select(func.count(ExtractedRow.id)).where(
                ExtractedRow.project_table_id == project_table_id
            )
        )
        or 0
    )


def _table_out(db: Session, t: ProjectTable) -> ProjectTableOut:
    return ProjectTableOut(
        id=t.id,
        project_id=t.project_id,
        template_id=t.template_id,
        name=t.name,
        columns=t.columns or [],
        row_count=_row_count(db, t.id),
        created_at=t.created_at,
    )


@router.get("/project-tables", response_model=list[ProjectTableOut])
def list_project_tables(
    project_id: str | None = None, db: Session = Depends(get_db)
) -> list[ProjectTableOut]:
    stmt = select(ProjectTable).order_by(ProjectTable.created_at.desc())
    if project_id:
        stmt = stmt.where(ProjectTable.project_id == project_id)
    return [_table_out(db, t) for t in db.scalars(stmt).all()]


@router.post("/project-tables", response_model=ProjectTableOut)
def create_project_table(
    payload: ProjectTableIn, db: Session = Depends(get_db)
) -> ProjectTableOut:
    project = db.get(Project, payload.project_id)
    if project is None:
        raise AppError("PROJECT_NOT_FOUND", "Projet introuvable.", status_code=404)
    template = db.get(TableTemplate, payload.template_id)
    if template is None:
        raise AppError("TEMPLATE_NOT_FOUND", "Modele introuvable.", status_code=404)
    t = ProjectTable(
        project_id=project.id,
        template_id=template.id,
        name=(payload.name or template.name).strip(),
        columns=template.columns or [],  # snapshot fige
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _table_out(db, t)


@router.get("/project-tables/{table_id}", response_model=ProjectTableOut)
def get_project_table(table_id: str, db: Session = Depends(get_db)) -> ProjectTableOut:
    t = db.get(ProjectTable, table_id)
    if t is None:
        raise AppError("TABLE_NOT_FOUND", "Table introuvable.", status_code=404)
    return _table_out(db, t)


@router.delete("/project-tables/{table_id}", status_code=204)
def delete_project_table(table_id: str, db: Session = Depends(get_db)) -> None:
    t = db.get(ProjectTable, table_id)
    if t is None:
        raise AppError("TABLE_NOT_FOUND", "Table introuvable.", status_code=404)
    db.query(ExtractedRow).filter(ExtractedRow.project_table_id == table_id).delete()
    db.delete(t)
    db.commit()


# ----- Lignes extraites -----------------------------------------------------


@router.get("/project-tables/{table_id}/rows", response_model=list[RowOut])
def list_rows(table_id: str, db: Session = Depends(get_db)) -> list[RowOut]:
    if db.get(ProjectTable, table_id) is None:
        raise AppError("TABLE_NOT_FOUND", "Table introuvable.", status_code=404)
    rows = db.scalars(
        select(ExtractedRow)
        .where(ExtractedRow.project_table_id == table_id)
        .order_by(ExtractedRow.created_at.asc())
    ).all()
    return [
        RowOut(
            id=r.id,
            source_filename=r.source_filename or "",
            values=r.values or {},
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.delete("/rows/{row_id}", status_code=204)
def delete_row(row_id: str, db: Session = Depends(get_db)) -> None:
    r = db.get(ExtractedRow, row_id)
    if r is None:
        raise AppError("ROW_NOT_FOUND", "Ligne introuvable.", status_code=404)
    db.delete(r)
    db.commit()
