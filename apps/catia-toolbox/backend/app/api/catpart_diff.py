"""Name-independent CATPart folder comparison endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import onedrive
from app.core.catpart_diff import compare_folders
from app.core.errors import AppError
from app.core.security import safe_under_root
from app.db.session import get_db

router = APIRouter(prefix="/diff", tags=["diff"])


class CatpartCompareIn(BaseModel):
    old_path: str = Field(min_length=1, max_length=4096)
    new_path: str = Field(min_length=1, max_length=4096)


class CatpartExactMatchOut(BaseModel):
    sha256: str
    old_files: list[str]
    new_files: list[str]
    old_count: int
    new_count: int


class CatpartCandidateOut(BaseModel):
    old_file: str
    new_file: str
    similarity: float = Field(ge=0, le=100)
    confidence: Literal["low"]
    old_geometry_quality: Literal["partial", "complete"]
    new_geometry_quality: Literal["partial", "complete"]
    binary_equal: bool


class CatpartIssueOut(BaseModel):
    file: str | None
    code: str
    message: str


class CatpartReaderOut(BaseModel):
    available: bool
    required: bool


class CatpartCompareOut(BaseModel):
    status: Literal["complete", "partial", "empty"]
    old_count: int
    new_count: int
    exact_matches: list[CatpartExactMatchOut]
    candidates: list[CatpartCandidateOut]
    unmatched_old: list[str]
    unmatched_new: list[str]
    issues: list[CatpartIssueOut]
    reader: CatpartReaderOut


@router.post("/catparts", response_model=CatpartCompareOut)
def compare_catpart_folders(body: CatpartCompareIn, db: Session = Depends(get_db)) -> dict[str, object]:
    root = onedrive.root_for_scope(db, "input")
    old_path = safe_under_root(root, body.old_path)
    new_path = safe_under_root(root, body.new_path)
    if old_path == new_path:
        raise AppError("CATPART_SAME_FOLDER", "Selectionnez deux dossiers differents.", status_code=400)
    return compare_folders(old_path, new_path)
