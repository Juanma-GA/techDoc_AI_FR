"""Tests unitaires purs - generation du plan (CSV + scripts dry-run)."""

from __future__ import annotations

from app.core.plan_export import to_bat, to_csv, to_sh


_SUGGESTIONS = [
    {"old_path": "vieux/PIECE 1.CATPart", "new_path": "by-type/catpart/piece-1.CATPart",
     "action": "group", "confidence": "moyenne", "rationale": "regroupement"},
    {"old_path": "x/keep.txt", "new_path": "x/keep.txt", "action": "keep",
     "confidence": "elevee", "rationale": "inchange"},
]


def test_to_csv_header_and_rows() -> None:
    out = to_csv(_SUGGESTIONS)
    lines = out.strip().splitlines()
    assert lines[0] == "old_path;new_path;action;confidence;rationale"
    assert any("by-type/catpart/piece-1.CATPart" in line for line in lines)


def test_to_bat_dryrun_no_destruction() -> None:
    out = to_bat(_SUGGESTIONS)
    assert "DRY-RUN" in out
    assert "mkdir" in out
    assert "move" in out
    # backslashes Windows
    assert "by-type\\catpart" in out
    # jamais de suppression
    assert "del " not in out.lower()
    assert "rmdir" not in out.lower()
    # l'action keep n'est pas appliquee
    assert "keep.txt" not in out


def test_to_sh_dryrun_no_destruction() -> None:
    out = to_sh(_SUGGESTIONS)
    assert "DRY-RUN" in out
    assert "mkdir -p" in out
    assert "mv " in out
    assert "set -euo pipefail" in out
    assert "rm " not in out
    assert "rm -" not in out


def test_empty_plan_has_no_commands() -> None:
    assert "Aucune suggestion" in to_bat([])
    assert "Aucune suggestion" in to_sh([])
