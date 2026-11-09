from __future__ import annotations

from pathlib import Path

import pytest

from app.flow import theme


@pytest.mark.parametrize("layout", ("framework", "standalone"))
def test_tokens_path_supports_consumer_and_standalone_layouts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    layout: str,
) -> None:
    source = tmp_path / "apps" / "flowchart-generator" / "backend" / "app" / "flow" / "theme.py"
    source.parent.mkdir(parents=True)
    source.touch()

    token_dir = (
        tmp_path / "framework" / "design-tokens"
        if layout == "framework"
        else tmp_path / "design-tokens"
    )
    token_dir.mkdir(parents=True)
    tokens = token_dir / "tokens.json"
    tokens.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(theme, "__file__", str(source))

    resolved = theme._tokens_path()
    assert resolved is not None and resolved.samefile(tokens)
