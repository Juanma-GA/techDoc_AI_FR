"""Pydantic request and response models for the comparison API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class ComparisonListItem(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    file_count: int
    ai_status: str


class ComparisonSummary(BaseModel):
    summary: str
    key_changes: list[str]
    impact: str


class ComparisonDetail(ComparisonListItem):
    report: dict[str, Any]
    ai_summary: ComparisonSummary | None
    ai_summary_truncated: bool


class SynthesisIn(BaseModel):
    language: Literal["fr", "en"] = "fr"


class SynthesisOut(BaseModel):
    ai_status: str
    ai_summary: ComparisonSummary | None
    ai_summary_truncated: bool
