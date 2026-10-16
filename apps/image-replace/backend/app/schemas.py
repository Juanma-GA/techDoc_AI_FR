"""Pydantic v2 I/O schemas - un modele par body / response."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str
    db: str


# ----- Settings -------------------------------------------------------------


class SettingsIn(BaseModel):
    demo_enabled: Optional[bool] = None


class SettingsOut(BaseModel):
    demo_enabled: bool


# ----- Admin (stats + reset) ------------------------------------------------


class AdminStatsOut(BaseModel):
    """Documents count startup workbooks; sessions/messages count image workspaces/operations."""

    documents: int = 0
    chunks: int = 0
    sessions: int = 0
    messages: int = 0
    total_size_bytes: int = 0


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]
