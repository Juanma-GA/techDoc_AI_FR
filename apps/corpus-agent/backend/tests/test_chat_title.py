from __future__ import annotations

from app.core.chat_engine import _session_title


def test_session_title_uses_two_or_three_meaningful_words() -> None:
    title = _session_title("Comment vérifier les références BASL dans le corpus ?")

    assert title == "Vérifier références BASL"
    assert len(title.split()) == 3


def test_session_title_stays_short_for_long_questions() -> None:
    title = _session_title(
        "Can you compare every maintenance procedure against the approved reference?"
    )

    assert title == "Compare every maintenance"
    assert len(title.split()) <= 3


def test_session_title_has_a_fallback_for_empty_questions() -> None:
    assert _session_title("?!") == "Nouvelle conversation"
