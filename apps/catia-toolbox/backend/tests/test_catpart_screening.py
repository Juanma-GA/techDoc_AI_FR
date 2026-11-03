from __future__ import annotations

from pathlib import Path

from app.core import catpart_diff, catpart_geometry

_STEP = """ISO-10303-21;
DATA;
#1 = CARTESIAN_POINT('', (0., 0., 0.));
#2 = CARTESIAN_POINT('', (1., 0., 0.));
#3 = CARTESIAN_POINT('', (0., 1., 0.));
#4 = PLANE('', #3);
ENDSEC;
END-ISO-10303-21;
"""


def _write_catpart(root: Path, filename: str) -> None:
    path = root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic CATPart")


def test_geometry_signature_ignores_translation_and_uniform_scale() -> None:
    transformed = _STEP.replace("(0., 0., 0.)", "(10., 20., 30.)")
    transformed = transformed.replace("(1., 0., 0.)", "(12., 20., 30.)")
    transformed = transformed.replace("(0., 1., 0.)", "(10., 22., 30.)")

    first = catpart_geometry.parse_step_signature(_STEP)
    second = catpart_geometry.parse_step_signature(transformed)

    assert first is not None and second is not None
    assert first.quality == "partial"
    assert catpart_geometry.geometry_similarity(first, second) == 100


def test_same_ge_and_ignored_non_ge_files_are_classified_separately(tmp_path: Path) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    same_ge = "GE_050N9_9994M99P01_UNCHANGED.CATPart"
    for root in (old_root, new_root):
        _write_catpart(root, same_ge)
        _write_catpart(root, "ordinary.CATPart")
    _write_catpart(old_root, "legacy-name.CATPart")
    _write_catpart(new_root, "new-name.CATPart")

    result = catpart_diff.compare_folders(old_root, new_root)

    assert result["same_ge"] == [
        {"sin": "050N9", "pn": "9994M99P01", "old_files": [same_ge], "new_files": [same_ge]}
    ]
    assert result["matches"] == []
    assert result["issues"] == []


def test_ge_with_same_sin_and_pn_is_classified_as_same_ge(tmp_path: Path) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    old_file = "GE_050N9_9994M99P01_SEAL.CATPart"
    new_file = "GE_050N9_9994M99P01_WIRE.CATPart"
    _write_catpart(old_root, old_file)
    _write_catpart(new_root, new_file)

    result = catpart_diff.compare_folders(old_root, new_root)

    assert result["same_ge"] == [
        {"sin": "050N9", "pn": "9994M99P01", "old_files": [old_file], "new_files": [new_file]}
    ]
    assert result["matches"] == []


def test_ge_files_with_shared_sin_but_unshared_pns_stay_reviewable(tmp_path: Path) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    old_files = ["GE_050N9_111_OLD_A.CATPart", "GE_050N9_222_OLD_B.CATPart"]
    new_file = "GE_050N9_444_NEW.CATPart"
    for filename in old_files:
        _write_catpart(old_root, filename)
    _write_catpart(new_root, new_file)

    result = catpart_diff.compare_folders(old_root, new_root)

    assert result["matches"] == [
        {
            "sin": "050N9",
            "old_pns": ["111", "222"],
            "new_pns": ["444"],
            "old_files": old_files,
            "new_files": [new_file],
        }
    ]
    assert result["solo_a"] == []
    assert result["solo_b"] == []


def test_invalid_ge_identifier_is_reported_and_word_embedded_ge_is_ignored(tmp_path: Path) -> None:
    old_root = tmp_path / "old"
    new_root = tmp_path / "new"
    old_root.mkdir()
    new_root.mkdir()
    invalid_file = "GE_1234_9994M99P01_SEAL.CATPart"
    _write_catpart(old_root, "XGE_050N9_111PN_OLD.CATPart")
    _write_catpart(new_root, invalid_file)

    result = catpart_diff.compare_folders(old_root, new_root)

    assert result["solo_a"] == []
    assert result["solo_b"] == []
    assert result["issues"] == [
        {
            "file": invalid_file,
            "code": "GE_FILENAME_INVALID",
            "message": "Identifiant GE invalide; SIN de 5 caracteres et PN alphanumerique attendus.",
        }
    ]
