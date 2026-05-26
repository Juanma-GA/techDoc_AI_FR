"""Static preview page served when the Vite dist isn't present.

Used by the .bat flow (no Node available) — the page consumes CSS variables
injected at request-time from `design-tokens/tokens.json`, so no hex literal
lives in this code.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import HTMLResponse


# apps/pdf-reviewer/backend/app/api/preview.py → 5 levels up = repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
_TOKENS_PATH = _REPO_ROOT / "design-tokens" / "tokens.json"
_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "preview.html"

_VARS_PLACEHOLDER = "/*__CSS_VARS__*/"


def _build_css_vars() -> str:
    """Émet :
      - `:root { … }` avec la palette dark (default + applied quand `<html class="dark">`)
      - `:root:not(.dark), .light { … }` avec les overrides light depuis
        `tokens.themes.light.color`. Les valeurs absentes côté light tombent
        sur leur valeur dark (no-op visuel).
    """
    tokens = json.loads(_TOKENS_PATH.read_text(encoding="utf-8"))
    color = tokens["color"]
    light_color = tokens.get("themes", {}).get("light", {}).get("color", {})
    layout = tokens["layout"]
    shadow = tokens["shadow"]
    accent = color.get("accent", {})

    def _light(path: tuple[str, ...]) -> str | None:
        node: object = light_color
        for seg in path:
            if not isinstance(node, dict):
                return None
            node = node.get(seg)
        return node if isinstance(node, str) else None

    # Liste canonique partagée entre tous les POCs — uniformité visuelle inter-apps.
    # Toute nouvelle var doit être ajoutée ici ET dans la liste équivalente des
    # autres preview.py des autres POCs. Source : design-tokens/tokens.json.
    color_pairs: list[tuple[str, str, tuple[str, ...]]] = [
        ("bg",            color["bg"]["base"],                                       ("bg", "base")),
        ("bg-2",          color["bg"]["2"],                                          ("bg", "2")),
        ("bg-3",          color["bg"]["3"],                                          ("bg", "3")),
        ("card",          color["card"]["base"],                                     ("card", "base")),
        ("card-hover",    color["card"]["hover"],                                    ("card", "hover")),
        ("brand",         color["brand"]["blue"],                                    ("brand", "blue")),
        ("brand-light",   color["brand"]["blue-light"],                              ("brand", "blue-light")),
        ("fg",            color["text"]["base"],                                     ("text", "base")),
        ("fg-dim",        color["text"]["dim"],                                      ("text", "dim")),
        ("fg-muted",      color["text"]["muted"],                                    ("text", "muted")),
        ("border",        color["border"]["base"],                                   ("border", "base")),
        ("border-bright", color["border"]["bright"],                                 ("border", "bright")),
        ("success",       color["semantic"]["success"],                              ("semantic", "success")),
        ("warning",       color["semantic"]["warning"],                              ("semantic", "warning")),
        ("danger",        color["semantic"]["danger"],                               ("semantic", "danger")),
        ("info",          color["semantic"]["info"],                                 ("semantic", "info")),
        ("accent-teal",   accent.get("teal",   color["semantic"]["info"]),           ("accent", "teal")),
        ("accent-purple", accent.get("purple", color["brand"]["blue-light"]),        ("accent", "purple")),
        ("accent-orange", accent.get("orange", color["semantic"]["warning"]),        ("accent", "orange")),
        ("accent-pink",   accent.get("pink",   color["semantic"]["danger"]),         ("accent", "pink")),
        ("accent-yellow", accent.get("yellow", color["semantic"]["warning"]),        ("accent", "yellow")),
    ]

    dark_lines = [f"  --{name}: {dark_val};" for name, dark_val, _ in color_pairs]
    light_lines = [
        f"  --{name}: {_light(path) or dark_val};"
        for name, dark_val, path in color_pairs
    ]

    layout_lines = [
        f"  --sidebar-w: {layout['sidebar-w']};",
        f"  --shadow-card: {shadow['card']};",
    ]

    # Pattern Tailwind classique : :root = light par défaut, .dark override.
    # Specificité égale (0,1,0), source order garantit le bon override.
    return (
        ":root {\n"
        + "\n".join(light_lines + layout_lines)
        + "\n}\n\n"
        ".dark {\n"
        + "\n".join(dark_lines)
        + "\n}"
    )


def render_preview() -> HTMLResponse:
    if not _TOKENS_PATH.is_file():
        raise HTTPException(status_code=500, detail="design-tokens/tokens.json introuvable")
    if not _TEMPLATE_PATH.is_file():
        raise HTTPException(status_code=500, detail="preview template introuvable")

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace(_VARS_PLACEHOLDER, _build_css_vars())
    return HTMLResponse(content=html)
