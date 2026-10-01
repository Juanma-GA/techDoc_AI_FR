"""Rules CRUD — including invalid regex rejection."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_legacy_demo_rules_are_not_seeded(client: TestClient) -> None:
    response = client.get("/api/v1/rules")

    assert response.status_code == 200
    names = {rule["name"] for rule in response.json()}
    assert names.isdisjoint(
        {
            "Pas d'oubli d'espace après ponctuation",
            "Pas de mot en MAJUSCULES",
            "Pas d'oubli d'accent (mots FR fréquents)",
        }
    )


def test_create_and_list_rule(client: TestClient) -> None:
    create = client.post(
        "/api/v1/rules",
        json={
            "name": "Use 'shall' not 'must'",
            "kind": "term_replace",
            "pattern": "must",
            "replacement": "shall",
            "severity": "warning",
            "message": "Préférer 'shall' (S1000D)",
        },
    )
    assert create.status_code == 201, create.text
    rule = create.json()
    assert rule["name"] == "Use 'shall' not 'must'"

    listing = client.get("/api/v1/rules")
    assert listing.status_code == 200
    assert any(r["id"] == rule["id"] for r in listing.json())


def test_create_rejects_invalid_regex(client: TestClient) -> None:
    response = client.post(
        "/api/v1/rules",
        json={
            "name": "Bad regex",
            "kind": "regex_replace",
            "pattern": "(unbalanced",
            "replacement": "x",
            "severity": "warning",
            "message": "",
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "RULE_PATTERN_INVALID"


def test_patch_and_delete(client: TestClient) -> None:
    create = client.post(
        "/api/v1/rules",
        json={
            "name": "tmp",
            "kind": "regex_flag",
            "pattern": r"\bTODO\b",
            "severity": "info",
            "message": "Not for production",
        },
    )
    assert create.status_code == 201
    rid = create.json()["id"]

    patch = client.patch(f"/api/v1/rules/{rid}", json={"enabled": False})
    assert patch.status_code == 200
    assert patch.json()["enabled"] is False

    delete = client.delete(f"/api/v1/rules/{rid}")
    assert delete.status_code == 204


def test_suggest_rejects_when_scope_empty(client: TestClient) -> None:
    # `document_ids` scoped to a non-existent UUID → no doc in scope, regardless
    # of what other tests have left in the table.
    response = client.post(
        "/api/v1/rules/suggest",
        json={"document_ids": ["00000000-0000-0000-0000-000000000000"]},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "NO_DOCS_FOR_SUGGESTIONS"


def test_suggest_from_files_rejects_excess_file_count_without_analysis(
    client: TestClient,
) -> None:
    files = [
        ("files", (f"synthetic-{index}.pdf", b"synthetic", "application/pdf"))
        for index in range(21)
    ]

    response = client.post("/api/v1/rules/suggest/from-files", files=files)

    assert response.status_code == 413
    assert response.json()["code"] == "RULE_SUGGEST_TOO_MANY_DOCUMENTS"


def test_suggest_from_files_rejects_unreadable_input_without_partial_results(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/rules/suggest/from-files",
        files={"files": ("synthetic.txt", b"SYNTHETIC-CONTENT", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "RULE_SUGGEST_INPUT_INCOMPLETE"


def test_suggest_returns_filtered_rules(client: TestClient, sample_pdf_bytes: bytes) -> None:
    upload = client.post(
        "/api/v1/documents",
        files={"file": ("manual.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["id"]

    with patch(
        "app.api.rules.suggest_rules_from_corpus",
        return_value=[
            {
                "name": "Use 'shall' not 'must'",
                "kind": "term_replace",
                "pattern": "must",
                "replacement": "shall",
                "severity": "warning",
                "message": "S1000D recommends 'shall'",
            },
        ],
    ):
        response = client.post(
            "/api/v1/rules/suggest",
            json={"document_ids": [doc_id]},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["documents_analyzed"] == 1
    assert len(body["suggestions"]) == 1
    assert body["suggestions"][0]["pattern"] == "must"
    assert body["suggestions"][0]["kind"] == "term_replace"
