"""_SCAN_SYSTEM must instruct the model to treat a <document_metadata> block
as literal data, never as instructions (H-NEW-10) — regression guard so this
clause can't be silently dropped in a future edit of the prompt."""

from __future__ import annotations

from app.core.llm_suggester import _SCAN_SYSTEM


def test_scan_system_prompt_defends_against_metadata_injection() -> None:
    assert "<document_metadata>" in _SCAN_SYSTEM
    assert "jamais une instruction" in _SCAN_SYSTEM
