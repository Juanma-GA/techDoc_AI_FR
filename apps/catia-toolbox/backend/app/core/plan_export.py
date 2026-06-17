"""Generation du plan de reorganisation : CSV + scripts relisables.

REGLE METIER : le POC ne deplace/renomme/supprime JAMAIS de fichier. Il
genere un PLAN (CSV) et un SCRIPT (.bat / .sh) que l'utilisateur relit puis
execute lui-meme. Aucune commande destructrice (`del`, `rm`) n'est generee.

Fonctions pures : acceptent des objets exposant `old_path`, `new_path`,
`action`, `rationale` (ORM Suggestion ou dataclass de test).
"""

from __future__ import annotations

import csv
import io
from typing import Any, Iterable


# Actions qui se traduisent par un deplacement de fichier (move/rename/group).
_MOVING_ACTIONS = {"move", "rename", "group"}


def _attr(s: Any, key: str, default: str = "") -> str:
    if isinstance(s, dict):
        return str(s.get(key, default))
    return str(getattr(s, key, default))


def _clean(path: str) -> str:
    """Retire guillemets et retours ligne — anti-injection dans le script."""
    return path.replace('"', "").replace("\n", " ").replace("\r", " ").strip()


def _parent_win(win_path: str) -> str:
    return win_path.rsplit("\\", 1)[0] if "\\" in win_path else ""


def _parent_posix(posix_path: str) -> str:
    return posix_path.rsplit("/", 1)[0] if "/" in posix_path else ""


def to_csv(suggestions: Iterable[Any]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["old_path", "new_path", "action", "confidence", "rationale"])
    for s in suggestions:
        writer.writerow(
            [
                _attr(s, "old_path"),
                _attr(s, "new_path"),
                _attr(s, "action"),
                _attr(s, "confidence"),
                _attr(s, "rationale").replace("\n", " "),
            ]
        )
    return buf.getvalue()


def to_bat(suggestions: Iterable[Any]) -> str:
    lines = [
        "@echo off",
        "REM ============================================================",
        "REM Plan de reorganisation - Catia Toolbox",
        "REM DRY-RUN : relisez ce script AVANT toute execution.",
        "REM Aucune suppression n'est generee (pas de del).",
        "REM BASE = racine de votre arborescence (defaut : dossier du script).",
        "REM ============================================================",
        "setlocal enabledelayedexpansion",
        'set "BASE=%~dp0"',
        "",
    ]
    count = 0
    for s in suggestions:
        if _attr(s, "action") not in _MOVING_ACTIONS:
            continue
        old = _clean(_attr(s, "old_path")).replace("/", "\\")
        new = _clean(_attr(s, "new_path")).replace("/", "\\")
        if not old or not new or old == new:
            continue
        count += 1
        new_parent = _parent_win(new)
        rationale = _clean(_attr(s, "rationale"))
        if rationale:
            lines.append(f"REM {rationale}")
        if new_parent:
            lines.append(f'if not exist "%BASE%{new_parent}" mkdir "%BASE%{new_parent}"')
        lines.append(f'move "%BASE%{old}" "%BASE%{new}"')
        lines.append("")
    if count == 0:
        lines.append("REM Aucune suggestion acceptee a appliquer.")
    lines.append("endlocal")
    return "\r\n".join(lines) + "\r\n"


def to_sh(suggestions: Iterable[Any]) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "# ============================================================",
        "# Plan de reorganisation - Catia Toolbox",
        "# DRY-RUN : relisez ce script AVANT toute execution.",
        "# Aucune suppression n'est generee (pas de rm).",
        "# Usage : bash plan.sh [BASE]  (BASE = racine, defaut : .)",
        "# ============================================================",
        "set -euo pipefail",
        'BASE="${1:-.}"',
        "",
    ]
    count = 0
    for s in suggestions:
        if _attr(s, "action") not in _MOVING_ACTIONS:
            continue
        old = _clean(_attr(s, "old_path"))
        new = _clean(_attr(s, "new_path"))
        if not old or not new or old == new:
            continue
        count += 1
        new_parent = _parent_posix(new)
        rationale = _clean(_attr(s, "rationale"))
        if rationale:
            lines.append(f"# {rationale}")
        if new_parent:
            lines.append(f'mkdir -p "$BASE/{new_parent}"')
        lines.append(f'mv "$BASE/{old}" "$BASE/{new}"')
        lines.append("")
    if count == 0:
        lines.append("# Aucune suggestion acceptee a appliquer.")
    return "\n".join(lines) + "\n"
