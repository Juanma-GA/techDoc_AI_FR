"""Preview HTML servi quand `frontend/dist/` n'existe pas (Node absent).

UI vanilla JS qui consomme directement les endpoints REST. Styling via
les CSS variables generees depuis design-tokens/tokens.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import HTMLResponse


# apps/doc-writer/backend/app/api/preview.py -> 5 levels up = repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
_TOKENS_PATH = _REPO_ROOT / "design-tokens" / "tokens.json"
_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "preview.html"
_LOCALES_FR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "frontend" / "src" / "locales" / "fr.json"
)


_VARS_PLACEHOLDER = "/*__CSS_VARS__*/"
_I18N_FR_PLACEHOLDER = "/*__I18N_FR__*/"


def _load_fr_translations() -> dict:
    if not _LOCALES_FR.is_file():
        return {}
    try:
        data = json.loads(_LOCALES_FR.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _build_css_vars() -> str:
    tokens = json.loads(_TOKENS_PATH.read_text(encoding="utf-8"))
    color = tokens["color"]
    light_color = tokens.get("themes", {}).get("light", {}).get("color", {})
    layout = tokens.get("layout", {})
    shadow = tokens.get("shadow", {})
    accent = color.get("accent", {})

    def _light(path):
        node = light_color
        for seg in path:
            if not isinstance(node, dict):
                return None
            node = node.get(seg)
        return node if isinstance(node, str) else None

    color_pairs = [
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
    ]

    dark_lines = [f"  --{name}: {dark_val};" for name, dark_val, _ in color_pairs]
    light_lines = [
        f"  --{name}: {_light(path) or dark_val};"
        for name, dark_val, path in color_pairs
    ]

    layout_lines = [
        f"  --sidebar-w: {layout.get('sidebar-w', '252px')};",
        f"  --shadow-card: {shadow.get('card', '0 1px 2px rgba(0,0,0,0.3)')};",
    ]

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
        raise HTTPException(
            status_code=500, detail="design-tokens/tokens.json introuvable"
        )
    if not _TEMPLATE_PATH.is_file():
        raise HTTPException(
            status_code=500, detail="preview template introuvable"
        )

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    css = _build_css_vars()
    fr_dict = _load_fr_translations()
    fr_json = json.dumps(fr_dict, ensure_ascii=False)
    html = template.replace(_VARS_PLACEHOLDER, css)
    html = html.replace(_I18N_FR_PLACEHOLDER, fr_json)
    # Preview en dev : on ne veut JAMAIS de cache navigateur, sinon un edit du
    # template ne se voit qu'apres Ctrl+F5.
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )
