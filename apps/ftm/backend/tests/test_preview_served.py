"""Régression : `/` doit servir le preview.html COMPLET par défaut.

Garde-fou contre le bug livré à l'IT (app vide) : tant que le front React est
une coquille, la racine doit rendre le preview complet — pas le SPA React —
sauf opt-in explicite via FTM_SERVE_SPA. Voir app/main.py::_mount_frontend.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_root_serves_complete_preview_by_default(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    body = response.text
    # Onglet « Vue Rédacteur » : marqueur que c'est bien le preview complet.
    assert 'data-page="redacteur"' in body
    # Les autres onglets métier attendus du preview.
    assert 'data-page="manager"' in body
    assert 'data-page="chatbot"' in body
    # Le placeholder i18n a bien été substitué (preview rendu, pas brut).
    assert "/*__I18N_FR__*/" not in body


def test_root_is_not_the_react_spa_index(client: TestClient) -> None:
    # Le SPA React n'est jamais servi sans FTM_SERVE_SPA : pas de bundle Vite.
    body = client.get("/").text
    assert "/assets/index-" not in body
