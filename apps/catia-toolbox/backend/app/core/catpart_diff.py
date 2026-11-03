"""Read-only CATPart screening using GE filename identifiers."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from app.core.catpart_names import GeCatPart, parse_ge_files, scan_catpart_folder
from app.core.errors import AppError


def compare_folders(old_root: Path, new_root: Path) -> dict[str, object]:
    old_folder = _validate_folder(old_root, "old")
    new_folder = _validate_folder(new_root, "new")
    if old_folder == new_folder:
        raise AppError("CATPART_SAME_FOLDER", "Selectionnez deux dossiers differents.", status_code=400)

    old_files = scan_catpart_folder(old_folder, "old")
    new_files = scan_catpart_folder(new_folder, "new")
    old_ge, old_issues = parse_ge_files(old_files)
    new_ge, new_issues = parse_ge_files(new_files)
    old_by_sin = _group_by_sin(old_ge)
    new_by_sin = _group_by_sin(new_ge)
    common_sins = old_by_sin.keys() & new_by_sin.keys()

    same_ge: list[dict[str, object]] = []
    matches: list[dict[str, object]] = []
    for sin_key in sorted(common_sins):
        old_by_pn = _group_by_pn(old_by_sin[sin_key])
        new_by_pn = _group_by_pn(new_by_sin[sin_key])
        common_pns = old_by_pn.keys() & new_by_pn.keys()
        sin = old_by_sin[sin_key][0].sin.upper()

        for pn_key in sorted(common_pns):
            same_ge.append(
                {
                    "sin": sin,
                    "pn": old_by_pn[pn_key][0].pn,
                    "old_files": [part.relative_path for part in old_by_pn[pn_key]],
                    "new_files": [part.relative_path for part in new_by_pn[pn_key]],
                }
            )

        old_remaining = [part for part in old_by_sin[sin_key] if part.pn.casefold() not in common_pns]
        new_remaining = [part for part in new_by_sin[sin_key] if part.pn.casefold() not in common_pns]
        if old_remaining or new_remaining:
            matches.append(
                {
                    "sin": sin,
                    "old_pns": [old_by_pn[key][0].pn for key in sorted(old_by_pn.keys() - common_pns)],
                    "new_pns": [new_by_pn[key][0].pn for key in sorted(new_by_pn.keys() - common_pns)],
                    "old_files": [part.relative_path for part in old_remaining],
                    "new_files": [part.relative_path for part in new_remaining],
                }
            )

    solo_a = [
        _solo_item(part) for part in old_ge if part.sin.casefold() not in new_by_sin
    ]
    solo_b = [
        _solo_item(part) for part in new_ge if part.sin.casefold() not in old_by_sin
    ]
    issues = [*old_issues, *new_issues]
    status = "empty" if not old_files or not new_files else ("partial" if issues else "complete")
    return {
        "status": status,
        "old_count": len(old_files),
        "new_count": len(new_files),
        "matches": matches,
        "same_ge": same_ge,
        "solo_a": solo_a,
        "solo_b": solo_b,
        "issues": issues,
    }


def _validate_folder(path: Path, side: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise AppError(
            "CATPART_FOLDER_NOT_FOUND",
            "Le dossier CATPart n'existe pas ou est inaccessible.",
            status_code=404,
            detail={"side": side},
        ) from exc
    if not resolved.is_dir():
        raise AppError(
            "CATPART_FOLDER_NOT_DIR",
            "Le chemin selectionne n'est pas un dossier.",
            status_code=400,
            detail={"side": side},
        )
    return resolved


def _group_by_sin(files: list[GeCatPart]) -> dict[str, list[GeCatPart]]:
    groups: dict[str, list[GeCatPart]] = defaultdict(list)
    for item in files:
        groups[item.sin.casefold()].append(item)
    return groups


def _group_by_pn(files: list[GeCatPart]) -> dict[str, list[GeCatPart]]:
    groups: dict[str, list[GeCatPart]] = defaultdict(list)
    for item in files:
        groups[item.pn.casefold()].append(item)
    return groups


def _solo_item(part: GeCatPart) -> dict[str, str]:
    return {"sin": part.sin.upper(), "pn": part.pn, "file": part.relative_path}
