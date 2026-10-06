"""Garde HTTP local-first : DNS rebinding, CSRF drive-by, exposition non
attestee, posture de demarrage, listes .env et fallback SPA sans acces UNC."""

from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.core.request_guard import CSRF_HEADER, CSRF_HEADER_VALUE
from app.db.models import Document
from app.db.session import SessionLocal
from app.main import create_app


# ---------------------------------------------------------------------------
# Garde HTTP : DNS rebinding (Host)
# ---------------------------------------------------------------------------


def test_foreign_host_header_is_rejected(client: TestClient) -> None:
    """Un domaine attaquant re-resolu vers 127.0.0.1 garde son nom dans Host."""
    response = client.get("/api/v1/documents", headers={"Host": "attacker.example:8003"})
    assert response.status_code == 400
    assert response.json()["code"] == "HOST_NOT_ALLOWED"


@pytest.mark.parametrize("host", ["127.0.0.1:8003", "localhost:8010", "[::1]:8003", "localhost"])
def test_loopback_hosts_are_accepted(client: TestClient, host: str) -> None:
    response = client.get("/api/v1/health", headers={"Host": host})
    assert response.status_code == 200


def test_allowed_hosts_setting_extends_the_allowlist(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "allowed_hosts", ["docrev.example"])
    assert client.get("/api/v1/health", headers={"Host": "docrev.example"}).status_code == 200
    assert client.get("/api/v1/health", headers={"Host": "other.example"}).status_code == 400

# ---------------------------------------------------------------------------
# Garde HTTP : CSRF « drive-by »
# ---------------------------------------------------------------------------


def _document_count() -> int:
    db = SessionLocal()
    try:
        return db.query(Document).count()
    finally:
        db.close()


def test_forged_admin_reset_without_csrf_header_is_rejected(
    client: TestClient, bare_client: TestClient, sample_pdf_bytes: bytes
) -> None:
    created = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert created.status_code == 201
    before = _document_count()

    # Formulaire HTML auto-soumis depuis un site tiers : pas d'en-tete perso.
    response = bare_client.post("/api/v1/admin/reset", headers={"Origin": "https://attacker.example"})
    assert response.status_code == 403
    assert _document_count() == before

    response = bare_client.post("/api/v1/admin/reset")
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_HEADER_MISSING"
    assert _document_count() == before


def test_forged_multipart_upload_is_rejected(bare_client: TestClient, sample_pdf_bytes: bytes) -> None:
    """Un multipart/form-data est une requete « simple » : pas de pre-vol CORS."""
    before = _document_count()
    response = bare_client.post(
        "/api/v1/documents",
        files={"file": ("evil.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 403
    assert _document_count() == before


def test_cross_origin_mutation_is_rejected_even_with_header(client: TestClient) -> None:
    response = client.post(
        "/api/v1/settings/vision",
        json={"enabled": False},
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ORIGIN_NOT_ALLOWED"

    response = client.post("/api/v1/settings/vision", json={"enabled": False}, headers={"Origin": "null"})
    assert response.status_code == 403


def test_same_origin_and_dev_origin_mutations_are_accepted(client: TestClient) -> None:
    same_origin = client.post(
        "/api/v1/settings/vision",
        json={"enabled": False},
        headers={"Origin": "http://127.0.0.1:8003"},
    )
    assert same_origin.status_code == 200
    dev_origin = client.post(
        "/api/v1/settings/vision",
        json={"enabled": False},
        headers={"Origin": "http://localhost:5173"},
    )
    assert dev_origin.status_code == 200


def test_reads_do_not_require_csrf_header(bare_client: TestClient) -> None:
    assert bare_client.get("/api/v1/health").status_code == 200


def test_cors_preflight_from_foreign_origin_is_not_allowed(bare_client: TestClient) -> None:
    response = bare_client.options(
        "/api/v1/admin/reset",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": CSRF_HEADER,
        },
    )
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers}

# ---------------------------------------------------------------------------
# Exposition non attestee (deploiement partage derriere proxy)
# ---------------------------------------------------------------------------


def test_proxied_request_is_rejected_without_auth_proxy_attestation(client: TestClient) -> None:
    """Cas atexispocs-cd : uvicorn force sur 127.0.0.1, mais nginx relaie."""
    response = client.get("/api/v1/documents", headers={"X-Forwarded-For": "172.21.28.10"})
    assert response.status_code == 403
    assert response.json()["code"] == "EXPOSURE_NOT_ALLOWED"
    assert client.get("/api/v1/health", headers={"Forwarded": "for=10.0.0.1"}).status_code == 403


def test_proxied_request_is_accepted_with_auth_proxy_attestation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "behind_auth_proxy", True)
    response = client.get("/api/v1/health", headers={"X-Forwarded-For": "172.21.28.10"})
    assert response.status_code == 200


def test_non_loopback_server_address_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bind 0.0.0.0 joint via l'IP du poste : refuse meme si BIND_HOST dit local."""
    monkeypatch.setattr(settings, "allowed_hosts", ["10.20.30.40"])
    exposed = TestClient(
        create_app(),
        base_url="http://10.20.30.40:8003",
        headers={CSRF_HEADER: CSRF_HEADER_VALUE},
    )
    response = exposed.get("/api/v1/health")
    assert response.status_code == 403
    assert response.json()["code"] == "EXPOSURE_NOT_ALLOWED"

# ---------------------------------------------------------------------------
# Posture de demarrage
# ---------------------------------------------------------------------------


_VALID_FERNET_KEY = "x" * 43 + "="


def test_exposed_bind_without_auth_proxy_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setattr(settings, "bind_host", "0.0.0.0")
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "cors_origins", ["https://docrev.example"])
    with pytest.raises(RuntimeError, match="BEHIND_AUTH_PROXY"):
        create_app()


def test_auth_proxy_deployment_on_loopback_still_requires_protections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BIND_HOST reste 127.0.0.1 (start-all.sh), mais l'instance est exposee."""
    monkeypatch.setattr(settings, "bind_host", "127.0.0.1")
    monkeypatch.setattr(settings, "behind_auth_proxy", True)
    monkeypatch.setattr(settings, "encryption_key", "")
    with pytest.raises(RuntimeError) as excinfo:
        create_app()
    message = str(excinfo.value)
    assert "ENCRYPTION_KEY" in message
    assert "CORS_ORIGINS" in message


def test_auth_proxy_deployment_starts_when_protections_are_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setattr(settings, "behind_auth_proxy", True)
    monkeypatch.setattr(settings, "encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "cors_origins", ["https://docrev.example"])
    create_app()


def test_invalid_encryption_key_is_refused_even_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une cle invalide rendait la cle Mistral stockee silencieusement « absente »."""
    monkeypatch.setattr(settings, "bind_host", "127.0.0.1")
    monkeypatch.setattr(settings, "encryption_key", "not-a-valid-fernet-key-but-long-enough-xx")
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY invalide"):
        create_app()

# ---------------------------------------------------------------------------
# Listes .env (CORS_ORIGINS, ALLOWED_HOSTS, MISTRAL_ALLOWED_BASE_URLS)
# ---------------------------------------------------------------------------


def test_comma_separated_env_lists_are_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le format documente dans .env.example faisait echouer le demarrage."""
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example, https://b.example")
    monkeypatch.setenv("ALLOWED_HOSTS", "docrev.example,docrev.example:8443")
    monkeypatch.setenv("MISTRAL_ALLOWED_BASE_URLS", "https://api.mistral.ai,https://llm.example/v")
    loaded = Settings()
    assert loaded.cors_origins == ["https://a.example", "https://b.example"]
    assert loaded.allowed_hosts == ["docrev.example", "docrev.example:8443"]
    assert loaded.mistral_allowed_base_urls == ["https://api.mistral.ai", "https://llm.example/v"]


def test_json_env_lists_remain_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["https://a.example"]')
    assert Settings().cors_origins == ["https://a.example"]

# ---------------------------------------------------------------------------
# Fallback SPA : aucun acces disque sur un chemin UNC / hors dist
# ---------------------------------------------------------------------------


@pytest.fixture
def spa_client(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> TestClient:
    from app import main

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    (dist / "robots.txt").write_text("User-agent: *", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("hors dist", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST", dist)
    return TestClient(
        main.create_app(),
        base_url="http://127.0.0.1:8003",
        headers={CSRF_HEADER: CSRF_HEADER_VALUE},
    )


def test_spa_fallback_never_resolves_unc_paths(
    spa_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved: list[str] = []
    original_resolve = pathlib.Path.resolve

    def _spy(self: pathlib.Path, *args: object, **kwargs: object) -> pathlib.Path:
        resolved.append(str(self))
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "resolve", _spy)
    for path in (
        "/%5C%5Cunc-host.invalid%5Cshare%5Cx.js",
        "/%5C%5C%3F%5CUNC%5Cunc-host.invalid%5Cshare",
        "/C:%5CWindows%5Cwin.ini",
        "/..%5Csecret.txt",
        "/index.html:stream",
    ):
        response = spa_client.get(path)
        assert response.status_code == 404, path
    assert not any("unc-host" in entry for entry in resolved)


def test_spa_fallback_still_serves_files_and_routes(spa_client: TestClient) -> None:
    assert spa_client.get("/robots.txt").text == "User-agent: *"
    route = spa_client.get("/documents/123")
    assert route.status_code == 200
    assert "spa" in route.text
    assert spa_client.get("/%2E%2E/secret.txt").status_code in {200, 404}
    assert "hors dist" not in spa_client.get("/%2E%2E/secret.txt").text
