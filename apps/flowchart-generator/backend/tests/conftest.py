"""Pytest fixtures - base SQLite temporaire, recreee proprement entre les tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="flowgen-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ["MISTRAL_API_KEY"] = ""


@pytest.fixture(autouse=True)
def _db():
    from app.db import models  # noqa: F401
    from app.db.session import Base, engine

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def app():
    from app.main import create_app

    return create_app()


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)


SAMPLE_DSL = """title: Batterie ne charge pas
system: Vehicule - circuit de charge
fault_code: P0562
lane Technicien
S [start] Voyant batterie allume
SEC [safety] Consigner le vehicule {securite: Couper le contact; outils: cales}
C1 [check] Tension batterie moteur tournant OK ? {attendu: 13,8 a 14,5 V; outils: multimetre; ref: DM-24-30}
R1 [repair] Remplacer l'alternateur {duree: 1 h 30}
V [check] Essai fonctionnel OK ? {attendu: 14 V}
end [end] Panne resolue
S -> SEC -> C1
C1 -> V : Oui
C1 -> R1 : Non
R1 -> V
V -> end : Oui
V -> C1 : Non
"""


@pytest.fixture
def sample_dsl() -> str:
    return SAMPLE_DSL
