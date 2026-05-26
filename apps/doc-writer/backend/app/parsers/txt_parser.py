"""Parseur texte brut (.txt, .md) : UTF-8 avec fallback latin-1."""

from __future__ import annotations

from pathlib import Path


def parse(path: str) -> dict[str, str]:
    data = Path(path).read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="replace")
    return {"text": text}
