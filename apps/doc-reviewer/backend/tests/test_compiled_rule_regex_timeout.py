"""L-09 hardening: every execution of a user-supplied regex against document
text must be bounded by `USER_REGEX_TIMEOUT_SECONDS`, never run unbounded.

`evaluate_regex`'s `require_all` branch had one unbounded `pattern.search(...)`
(no `timeout=`) in its fallback path (compiled_rule_operators.py:1139,
reached when `require_all` is satisfied but the first finditer pass never set
`first_match`). A user-supplied regex with catastrophic backtracking hitting
that exact line would hang the request instead of degrading to
`INCONCLUSIVE` like every other regex evaluation in this module."""

from __future__ import annotations

from app.core import compiled_rule_operators as ops
from app.core.compiled_rule_runtime import _EvalContext, _TextTarget
from app.core.compiled_rules import Check


class _FakeMatch:
    def group(self, _index: int = 0) -> str:
        return "matched"


class _FakePattern:
    """Matches on the first `search` (the require_all probe), then times out
    on any further call — exercising the fallback line in isolation without
    needing a real catastrophic-backtracking pattern."""

    def __init__(self) -> None:
        self.search_calls = 0

    def finditer(self, _text: str, timeout: float | None = None):
        return []  # no match in the first pass -> first_match stays None

    def search(self, _text: str, timeout: float | None = None):
        self.search_calls += 1
        if self.search_calls == 1:
            return _FakeMatch()
        raise TimeoutError


def _ctx() -> _EvalContext:
    return _EvalContext(
        all_targets=[],
        is_docx=True,
        blocks=None,
        pdf_pages=None,
        document=None,
        db=None,
    )


def test_require_all_fallback_search_is_bounded_by_the_regex_timeout(monkeypatch) -> None:
    monkeypatch.setattr(ops, "compile_user_regex", lambda _pattern: _FakePattern())

    check = Check(field="text", operator="regex_exists", expected="synthetic", require_all=True)
    target = _TextTarget(page="1", text="synthetic text", raw_page=1)

    status, result_target, matched_text, expected = ops.evaluate_regex(
        check, [(target, "synthetic text")], "RULE_SYNTHETIC", _ctx()
    )

    # Must degrade to INCONCLUSIVE (same contract as every other timeout in
    # this module) instead of letting the TimeoutError propagate uncaught.
    assert status == "INCONCLUSIVE"
    assert result_target is target
    assert matched_text is None
    assert expected == "synthetic"
