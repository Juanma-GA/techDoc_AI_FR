"""POST/GET/PATCH /api/v1/users — local accounts (H-NEW-04 remediation).

Covers: password hashes never leave the API, duplicate-email rejection,
login accepting only correct credentials (case-insensitive email), and
profile updates.
"""

from __future__ import annotations


def _register(client, name="Maria Ruiz", email="maria@atexis.com", password="S3cret!"):
    return client.post("/api/v1/users/register", json={"name": name, "email": email, "password": password})


def test_register_returns_user_without_password_fields(client) -> None:
    res = _register(client)
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "Maria Ruiz"
    assert body["email"] == "maria@atexis.com"
    assert "id" in body and "created_at" in body
    assert "password" not in body
    assert "password_hash" not in body
    assert "password_salt" not in body


def test_register_duplicate_email_rejected(client) -> None:
    assert _register(client, email="dup@atexis.com").status_code == 201
    res = _register(client, name="Other", email="dup@atexis.com", password="different")
    assert res.status_code == 409
    assert res.json()["code"] == "EMAIL_EXISTS"


def test_login_accepts_correct_credentials_case_insensitive_email(client) -> None:
    _register(client, email="jon@atexis.com", password="hunter2")
    res = client.post("/api/v1/users/login", json={"email": "JON@atexis.com", "password": "hunter2"})
    assert res.status_code == 200
    assert res.json()["email"] == "jon@atexis.com"


def test_login_rejects_wrong_password(client) -> None:
    _register(client, email="jon2@atexis.com", password="hunter2")
    res = client.post("/api/v1/users/login", json={"email": "jon2@atexis.com", "password": "nope"})
    assert res.status_code == 401
    assert res.json()["code"] == "INVALID_CREDENTIALS"


def test_login_rejects_unknown_email(client) -> None:
    res = client.post("/api/v1/users/login", json={"email": "ghost@atexis.com", "password": "x"})
    assert res.status_code == 401


def test_list_users_returns_all_registered(client) -> None:
    _register(client, name="A", email="a@atexis.com")
    _register(client, name="B", email="b@atexis.com")
    res = client.get("/api/v1/users")
    assert res.status_code == 200
    emails = {u["email"] for u in res.json()}
    assert {"a@atexis.com", "b@atexis.com"} <= emails


def test_update_profile_changes_name_and_email(client) -> None:
    created = _register(client, name="Old Name", email="old@atexis.com").json()
    res = client.patch(
        f"/api/v1/users/{created['id']}",
        json={"name": "New Name", "email": "new@atexis.com"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "New Name"
    assert body["email"] == "new@atexis.com"


def test_update_profile_rejects_email_taken_by_another_user(client) -> None:
    _register(client, email="taken@atexis.com")
    other = _register(client, email="other@atexis.com").json()
    res = client.patch(
        f"/api/v1/users/{other['id']}",
        json={"name": "Other", "email": "taken@atexis.com"},
    )
    assert res.status_code == 409


def test_update_profile_unknown_user_404(client) -> None:
    res = client.patch("/api/v1/users/u_doesnotexist", json={"name": "X", "email": "x@atexis.com"})
    assert res.status_code == 404
