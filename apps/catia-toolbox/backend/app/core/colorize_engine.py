"""Moteur de colorisation des pieces (couleurs RGB, dry-run).

Attribue une couleur RGB (0-255, format natif CATIA / Composer) a chaque piece
selon une strategie :
  - by_change : depuis une comparaison (ajoutees=vert, supprimees=rouge,
    modifiees=orange) -> mise en evidence des evolutions.
  - by_type   : une couleur par extension (palette deterministe).
  - by_depth  : degrade selon la profondeur dans l'arborescence.

Couleurs exprimees en triplets (r, g, b) - jamais en hexadecimal (regle #4).
Genere un CSV + une macro CATIA squelette (SetRealColor), jamais executee.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.core.parser import ParsedNode

STRATEGIES = ["by_change", "by_type", "by_depth"]

# Couleurs par etat (comparaison).
CHANGE_COLORS: dict[str, tuple[int, int, int]] = {
    "added": (0, 176, 80),      # vert
    "removed": (192, 0, 0),     # rouge
    "modified": (255, 153, 0),  # orange
    "unchanged": (190, 190, 190),  # gris
}

# Palette deterministe (cyclique) pour la colorisation par type.
_PALETTE: list[tuple[int, int, int]] = [
    (31, 119, 180),
    (255, 127, 14),
    (44, 160, 44),
    (214, 39, 40),
    (148, 103, 189),
    (140, 86, 75),
    (227, 119, 194),
    (127, 127, 127),
    (188, 189, 34),
    (23, 190, 207),
]


def colorize_by_change(entries: Iterable[dict]) -> list[dict]:
    out: list[dict] = []
    for e in entries:
        ct = e.get("change_type", "modified")
        r, g, b = CHANGE_COLORS.get(ct, CHANGE_COLORS["modified"])
        out.append({"rel_path": e["rel_path"], "r": r, "g": g, "b": b, "reason": f"etat: {ct}"})
    return out


def colorize_by_type(nodes: Iterable[ParsedNode]) -> list[dict]:
    files = [n for n in nodes if n.kind == "file"]
    exts = sorted({n.ext for n in files if n.ext})
    color_for = {ext: _PALETTE[i % len(_PALETTE)] for i, ext in enumerate(exts)}
    out: list[dict] = []
    for n in files:
        r, g, b = color_for.get(n.ext, (130, 130, 130))
        out.append({"rel_path": n.rel_path, "r": r, "g": g, "b": b, "reason": f"type: .{n.ext or 'sans'}"})
    return out


def colorize_by_depth(nodes: Iterable[ParsedNode]) -> list[dict]:
    files = [n for n in nodes if n.kind == "file"]
    max_depth = max((n.depth for n in files), default=0) or 1
    out: list[dict] = []
    for n in files:
        # Degrade bleu (peu profond) -> rouge (profond).
        ratio = min(1.0, n.depth / max_depth)
        r = int(40 + ratio * 200)
        b = int(220 - ratio * 200)
        out.append({"rel_path": n.rel_path, "r": r, "g": 80, "b": b, "reason": f"profondeur {n.depth}"})
    return out


def summarize(items: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {"total": len(items)}
    colors = {(i["r"], i["g"], i["b"]) for i in items}
    out["distinct_colors"] = len(colors)
    return out


def _attr(s: Any, key: str) -> str:
    return str(s.get(key, "") if isinstance(s, dict) else getattr(s, key, ""))


def _int(s: Any, key: str) -> int:
    v = s.get(key) if isinstance(s, dict) else getattr(s, key, 0)
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def to_csv(items: Iterable[Any]) -> str:
    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["rel_path", "r", "g", "b", "reason"])
    for it in items:
        w.writerow([
            _attr(it, "rel_path"),
            _int(it, "color_r") or _int(it, "r"),
            _int(it, "color_g") or _int(it, "g"),
            _int(it, "color_b") or _int(it, "b"),
            _attr(it, "reason"),
        ])
    return buf.getvalue()


def _text_color(r: int, g: int, b: int) -> str:
    """Noir ou blanc selon la luminance (lisibilite sur la couleur de fond)."""
    luminance = (r * 299 + g * 587 + b * 114) / 1000
    return "black" if luminance > 140 else "white"


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def to_svg(items: list[Any], *, cols: int = 6) -> str:
    """Simulation visuelle : une tuile coloree par piece (rendu SVG autonome).

    Donne une idee de l'aspect colorise sans CATIA. Couleurs en rgb(), texte en
    'black'/'white' - aucun hexadecimal (regle #4).
    """
    items = list(items)
    if not items:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="60">'
            '<text x="12" y="34" font-family="monospace" font-size="13">Aucune piece a coloriser.</text></svg>'
        )
    cols = max(1, min(cols, len(items)))
    tile_w, tile_h, pad = 150, 56, 8
    rows = (len(items) + cols - 1) // cols
    width = cols * (tile_w + pad) + pad
    height = rows * (tile_h + pad) + pad

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="monospace">'
    ]
    for i, it in enumerate(items):
        r = _int(it, "color_r") or _int(it, "r")
        g = _int(it, "color_g") or _int(it, "g")
        b = _int(it, "color_b") or _int(it, "b")
        x = (i % cols) * (tile_w + pad) + pad
        y = (i // cols) * (tile_h + pad) + pad
        name = _attr(it, "rel_path").rsplit("/", 1)[-1]
        if len(name) > 20:
            name = name[:19] + "…"
        txt = _text_color(r, g, b)
        parts.append(
            f'<rect x="{x}" y="{y}" width="{tile_w}" height="{tile_h}" rx="6" '
            f'fill="rgb({r},{g},{b})" stroke="rgb(0,0,0)" stroke-opacity="0.15"/>'
        )
        parts.append(
            f'<text x="{x + 8}" y="{y + tile_h // 2 + 4}" font-size="12" fill="{txt}">{_xml_escape(name)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def to_composer_pyscript(items: Iterable[Any]) -> str:
    """Script Python win32com appliquant les couleurs aux acteurs Composer.

    DRY_RUN=True par defaut. Le plan (chemin -> couleur RGB) est embarque.
    Les appels API exacts (recherche d'acteur, propriete couleur) sont a
    confirmer sur la version SDK Composer de l'utilisateur.
    """
    import json

    plan_lines = []
    for it in items:
        path = _attr(it, "rel_path")
        r = _int(it, "color_r") or _int(it, "r")
        g = _int(it, "color_g") or _int(it, "g")
        b = _int(it, "color_b") or _int(it, "b")
        name = path.rsplit("/", 1)[-1]
        if not path:
            continue
        plan_lines.append(f"    ({json.dumps(name)}, ({r}, {g}, {b}), {json.dumps(path)}),")
    plan_body = "\n".join(plan_lines) if plan_lines else "    # (aucune piece a coloriser)"
    return _COMPOSER_COLOR_TEMPLATE.replace("__PLAN__", plan_body)


_COMPOSER_COLOR_TEMPLATE = '''#!/usr/bin/env python
"""Colorisation des acteurs Composer via win32com - Catia Toolbox.

DRY-RUN : DRY_RUN=True par defaut, le script n'execute rien (affiche le plan).
Mettez DRY_RUN=False APRES relecture pour appliquer les couleurs.

A confirmer sur votre version Composer (cf. SDK / Composer Automation) :
  - COMPOSER_PROGID : ProgID COM du serveur Composer.
  - SMG_PATH : le document .smg cible a ouvrir.
  - la recherche d'acteur par nom et la propriete de couleur (set_color()).

Couleurs en RGB 0-255.
"""

from __future__ import annotations

import os
import sys

# --- Configuration (a adapter) ---------------------------------------------
DRY_RUN = True
COMPOSER_PROGID = "Composer.Application"  # TODO: confirmer le ProgID Composer
SMG_PATH = ""  # TODO: chemin du .smg a coloriser (ex: r"C:\\...\\assemblage.smg")

# Plan de colorisation : (nom acteur, (r, g, b), chemin d'origine).
PLAN = [
__PLAN__
]


def _log(msg, err=False):
    (sys.stderr if err else sys.stdout).write(str(msg) + "\\n")


def connect_composer():
    try:
        import win32com.client
    except ImportError:
        _log("ERREUR: pywin32 requis (pip install pywin32).", err=True)
        raise
    app = win32com.client.Dispatch(COMPOSER_PROGID)
    try:
        app.Visible = True
    except Exception:
        pass
    return app


def set_color(doc, actor_name: str, rgb) -> bool:
    """Applique une couleur RGB a l'acteur nomme. A adapter a l'API Composer."""
    r, g, b = rgb
    # TODO: adapter aux methodes reelles (recherche d'acteur + propriete couleur).
    actors = doc.GetActorsByName(actor_name)  # placeholder
    found = False
    for actor in actors:
        actor.SetColor(r, g, b)  # placeholder
        found = True
    return found


def main() -> int:
    _log(f"{len(PLAN)} piece(s) a coloriser. DRY_RUN={DRY_RUN}")
    if DRY_RUN:
        for name, rgb, path in PLAN:
            _log(f"  [color] {path} -> rgb{rgb}")
        return 0
    if not SMG_PATH or not os.path.isfile(SMG_PATH):
        _log("ERREUR: renseignez SMG_PATH (document .smg a ouvrir).", err=True)
        return 1
    app = connect_composer()
    doc = app.Documents.Open(SMG_PATH)
    ok = 0
    for name, rgb, path in PLAN:
        try:
            if set_color(doc, name, rgb):
                ok += 1
            else:
                _log(f"    acteur introuvable: {name}", err=True)
        except Exception as exc:  # noqa: BLE001
            _log(f"    ECHEC {name}: {exc}", err=True)
    doc.Save()
    _log(f"Termine: {ok}/{len(PLAN)} colorise(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def to_macro(items: Iterable[Any]) -> str:
    """Squelette de macro CATIA (VBScript) appliquant les couleurs - dry-run."""
    lines = [
        "' ============================================================",
        "' Macro de colorisation - Catia Toolbox (squelette)",
        "' DRY-RUN : relisez et adaptez AVANT execution dans CATIA.",
        "' SetRealColor(r, g, b, inheritance) sur la selection courante.",
        "' ============================================================",
        "Sub CATMain()",
        "  Dim oSel : Set oSel = CATIA.ActiveDocument.Selection",
        "",
    ]
    count = 0
    for it in items:
        path = _attr(it, "rel_path").replace('"', "")
        r = _int(it, "color_r") or _int(it, "r")
        g = _int(it, "color_g") or _int(it, "g")
        b = _int(it, "color_b") or _int(it, "b")
        if not path:
            continue
        count += 1
        lines.append(f"  ' {path}")
        lines.append("  ' oSel.Clear : oSel.Add <produit/piece>")
        lines.append(f"  ' oSel.VisProperties.SetRealColor {r}, {g}, {b}, 1")
        lines.append("")
    if count == 0:
        lines.append("  ' Aucune piece a coloriser.")
    lines.append("End Sub")
    return "\r\n".join(lines) + "\r\n"
