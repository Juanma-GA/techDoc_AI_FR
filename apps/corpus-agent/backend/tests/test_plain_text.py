from __future__ import annotations

import pytest

from app.core.plain_text import PlainTextStream, strip_markdown


def test_strip_markdown_removes_markers() -> None:
    src = "## Synthèse\n**Motifs** récurrents : `TL-1002` et *faux positifs*.\n* item un\n- item deux"
    out = strip_markdown(src)
    assert "*" not in out and "#" not in out and "`" not in out
    assert out.startswith("Synthèse\nMotifs récurrents : TL-1002 et faux positifs.")
    assert "- item un" in out and "- item deux" in out


def test_strip_markdown_keeps_citations_and_underscores() -> None:
    assert strip_markdown("Voir [FTM_DEMO-32.xlsx] page 2") == "Voir [FTM_DEMO-32.xlsx] page 2"


@pytest.mark.parametrize("size", [1, 2, 3, 5])
def test_stream_matches_full_text_whatever_the_chunking(size: int) -> None:
    src = "# Titre\nUn **mot gras** et *italique* avec `code`.\n## Sous-titre\n* point\nFin **"
    stream = PlainTextStream()
    out = "".join(stream.feed(src[i:i + size]) for i in range(0, len(src), size)) + stream.flush()
    assert out == strip_markdown(src)
    assert "*" not in out and "#" not in out and "`" not in out
