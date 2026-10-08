"""Pydantic v2 I/O schemas - un modele par body / response."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    db: str


# ----- Admin (stats + reset) ------------------------------------------------


class AdminStatsOut(BaseModel):
    """Compteurs sommaires affiches dans l'onglet Donnees du preview.

    Les champs sont volontairement generiques : chaque POC peut surcharger
    `admin.stats()` pour compter ses propres tables. Les compteurs métier
    restent à zéro car ECM Automation n'enregistre pas de documents en base.
    """

    documents: int = 0
    chunks: int = 0
    sessions: int = 0
    messages: int = 0
    total_size_bytes: int = 0


class AdminResetOut(BaseModel):
    scope: str
    deleted: dict[str, int]
