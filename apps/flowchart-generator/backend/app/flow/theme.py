"""Palette d'export lue a l'execution depuis design-tokens/tokens.json (theme light).

Aucune couleur n'est ecrite en dur : les exports (documents imprimables) utilisent
le theme light des tokens. Repli sur des niveaux de gris RGB si le fichier manque.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.flow.model import NodeType

_RGB_FALLBACK = {
    "bg": (255, 255, 255),
    "panel": (241, 245, 249),
    "text": (15, 23, 42),
    "dim": (100, 116, 139),
    "line": (100, 116, 139),
    "start": (16, 185, 129),
    "end": (220, 38, 38),
    "process": (37, 99, 235),
    "decision": (217, 119, 6),
    "io": (8, 145, 178),
    "document": (124, 58, 237),
    "subprocess": (37, 99, 235),
    "connector": (100, 116, 139),
    "check": (2, 132, 199),
    "repair": (234, 88, 12),
    "safety": (202, 138, 4),
}


def _tokens_path() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "design-tokens" / "tokens.json"
        if candidate.is_file():
            return candidate
    return None


def _to_rgb(value: str) -> tuple[int, int, int] | None:
    v = value.strip().lstrip("#")
    if len(v) != 6:
        return None
    try:
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def palette() -> dict[str, tuple[int, int, int]]:
    pal = dict(_RGB_FALLBACK)
    path = _tokens_path()
    if path is None:
        return pal
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        light = data["themes"]["light"]["color"]
    except (OSError, ValueError, KeyError):
        return pal
    mapping = {
        # Printable pages keep a white background: the light app background is tinted.
        "bg": light["card"]["base"],
        "panel": light["card"]["hover"],
        "text": light["text"]["base"],
        "dim": light["text"]["dim"],
        "line": light["text"]["dim"],
        "start": light["semantic"]["success"],
        "end": light["semantic"]["danger"],
        "process": light["brand"]["blue"],
        "decision": light["semantic"]["warning"],
        "io": light["accent"]["teal"],
        "document": light["accent"]["purple"],
        "subprocess": light["brand"]["blue-light"],
        "connector": light["text"]["dim"],
        "check": light["semantic"]["info"],
        "repair": light["accent"]["orange"],
        "safety": light["accent"]["yellow"],
    }
    for key, raw in mapping.items():
        rgb = _to_rgb(str(raw))
        if rgb:
            pal[key] = rgb
    return pal


def hex6(key: str) -> str:
    """Couleur sans diese (openpyxl / python-pptx)."""
    r, g, b = palette()[key]
    return f"{r:02X}{g:02X}{b:02X}"


def css(key: str) -> str:
    """Couleur au format CSS (SVG, draw.io)."""
    return "#" + hex6(key)


def tint(key: str, ratio: float = 0.85) -> tuple[int, int, int]:
    """Melange avec le blanc pour les fonds de formes."""
    r, g, b = palette()[key]
    return tuple(int(c + (255 - c) * ratio) for c in (r, g, b))  # type: ignore[return-value]


def tint_hex(key: str, ratio: float = 0.85) -> str:
    r, g, b = tint(key, ratio)
    return f"{r:02X}{g:02X}{b:02X}"


def fill_key(node_type: NodeType) -> str:
    return node_type.value
