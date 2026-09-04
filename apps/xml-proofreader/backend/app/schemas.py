"""Pydantic v2 I/O schemas - un modele par body / response."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    llm: str


# ----- Settings (Mistral runtime config) ------------------------------------


class SettingsIn(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    chat_model: Optional[str] = None
    embed_model: Optional[str] = None
    llm_enabled: Optional[bool] = None


class SettingsOut(BaseModel):
    api_key_set: bool
    base_url: str
    chat_model: str
    embed_model: str
    llm_enabled: bool
    llm_tested: bool = False


class TestConnectionOut(BaseModel):
    ok: bool
    models: list[str] = Field(default_factory=list)
    error: Optional[str] = None


# ----- Users (local accounts, per-workstation profiles) ---------------------


class UserOut(BaseModel):
    """Public user shape. Never carries password_hash/password_salt."""

    id: str
    name: str
    email: str
    created_at: int


class UserRegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class UserLoginIn(BaseModel):
    email: str
    password: str


class UserUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)


# ----- Admin (stats + reset) ------------------------------------------------


class AdminStatsOut(BaseModel):
    """Compteurs sommaires affiches dans l'onglet Donnees du preview.

    Les champs sont volontairement generiques : chaque POC peut surcharger
    `admin.stats()` pour compter ses propres tables. Pour le xml-proofreader,
    tout est a 0.
    """

    documents: int = 0
    chunks: int = 0
    sessions: int = 0
    messages: int = 0
    total_size_bytes: int = 0


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]
