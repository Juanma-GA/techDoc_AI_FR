"""Fiabilisation LLM : endpoint /settings/reliability + budget + feedback +
comportement du verifier quand le LLM est indisponible."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.checks.raw import RawSuggestion
from app.core import feedback
from app.core.llm_budget import LlmBudget


def _raw(code: str, original: str) -> RawSuggestion:
    return RawSuggestion(
        rule_kind="custom" if code == "AI_SCAN" else "standard",
        rule_code=code,
        severity="warning",
        message="m",
        original=original,
        proposed="x",
        page=1,
        span=(0, len(original)),
    )


# ---- Endpoint /settings/reliability --------------------------------------


def test_reliability_defaults(client: TestClient) -> None:
    r = client.get("/api/v1/settings/reliability")
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "verify_enabled": True,
        "verify_passes": 3,
        "max_calls": 400,
        "feedback_enabled": True,
    }


def test_reliability_update_and_clamp(client: TestClient) -> None:
    # passes clampé à [1,5], max_calls à [0,5000].
    r = client.post(
        "/api/v1/settings/reliability",
        json={"verify_enabled": False, "verify_passes": 99, "max_calls": -10, "feedback_enabled": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verify_enabled"] is False
    assert body["verify_passes"] == 5  # clamp haut
    assert body["max_calls"] == 0  # clamp bas
    assert body["feedback_enabled"] is False
    # persistance
    assert client.get("/api/v1/settings/reliability").json()["verify_passes"] == 5


# ---- Budget ---------------------------------------------------------------


def test_budget_caps_calls() -> None:
    b = LlmBudget(2)
    assert b.spend() is True
    assert b.spend() is True
    assert b.spend() is False
    assert b.remaining() == 0


def test_budget_zero_blocks_immediately() -> None:
    b = LlmBudget(0)
    assert b.spend() is False


# ---- Feedback global (scope AI_SCAN uniquement) ---------------------------


def test_feedback_filters_only_ai_findings() -> None:
    exclusions = {("AI_SCAN", "faux positif")}
    raws = [
        _raw("AI_SCAN", "faux positif"),   # exclu
        _raw("AI_SCAN", "vrai souci"),     # garde
        _raw("STE_PASSIVE_VOICE", "faux positif"),  # deterministe -> jamais filtre
    ]
    kept = feedback.filter_excluded(raws, exclusions)
    codes = [(r.rule_code, r.original) for r in kept]
    assert ("AI_SCAN", "faux positif") not in codes
    assert ("AI_SCAN", "vrai souci") in codes
    assert ("STE_PASSIVE_VOICE", "faux positif") in codes


def test_feedback_noop_without_exclusions() -> None:
    raws = [_raw("AI_SCAN", "x")]
    assert feedback.filter_excluded(raws, set()) == raws


# ---- Verifier : LLM indisponible -> on GARDE le finding -------------------


def test_verifier_keeps_finding_when_llm_unavailable(client: TestClient) -> None:
    # LLM desactive -> call_chat leve AppError (aucun appel reseau) ->
    # _refute_once renvoie False (pas de refutation a tort) -> survives True.
    from app.core import verifier
    from app.core.mistral_settings import set_llm_enabled
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        set_llm_enabled(db, False)
        f = _raw("AI_SCAN", "une phrase a verifier")
        assert verifier.survives(db, f, LlmBudget(10), passes=3) is True
    finally:
        set_llm_enabled(db, True)
        db.close()
