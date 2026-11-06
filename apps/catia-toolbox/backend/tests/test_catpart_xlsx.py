from __future__ import annotations

from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from app.api import catpart_diff as catpart_diff_api


def _write_catpart(root: Path, filename: str) -> None:
    path = root / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic CATPart")


def test_export_xlsx_contains_common_and_solo_sheets(
    client,
    tmp_path: Path,
    monkeypatch,
) -> None:
    input_root = tmp_path / "input"
    old_root = input_root / "old"
    new_root = input_root / "new"
    old_root.mkdir(parents=True)
    new_root.mkdir(parents=True)
    old_same = "=GE_X-050N9-111PN_OLD.CATPart"
    new_same = "GE-A_050N9_111PN_NEW.CATPart"
    old_changed = "prefix-GE_050N9_222PN_OLD.CATPart"
    new_changed = "GE-050N9-333PN_NEW.CATPart"
    solo_a = "GE_101A2_444PN_ONLY_A.CATPart"
    solo_b = "GE_X-202B3-555PN_ONLY_B.CATPart"
    for filename in (old_same, old_changed, solo_a):
        _write_catpart(old_root, filename)
    for filename in (new_same, new_changed, solo_b):
        _write_catpart(new_root, filename)
    monkeypatch.setattr(
        catpart_diff_api.onedrive,
        "root_for_scope",
        lambda db, scope: str(input_root),
    )

    response = client.post(
        "/api/v1/diff/catparts/export.xlsx",
        json={"old_path": str(old_root), "new_path": str(new_root)},
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == catpart_diff_api.XLSX_MEDIA_TYPE
    workbook = load_workbook(BytesIO(response.content), read_only=True, data_only=True)
    assert workbook.sheetnames == ["GE communs", "Solo A", "Solo B"]

    common_rows = list(workbook["GE communs"].iter_rows(values_only=True))
    assert common_rows[1] == (
        "GE pareil",
        "050N9",
        "111PN",
        "111PN",
        old_same,
        new_same,
    )
    assert common_rows[2] == (
        "SIN commun, PN différent",
        "050N9",
        "222PN",
        "333PN",
        old_changed,
        new_changed,
    )
    assert workbook["GE communs"]["E2"].data_type == "s"
    assert list(workbook["Solo A"].iter_rows(min_row=2, values_only=True)) == [
        ("101A2", "444PN", solo_a)
    ]
    assert list(workbook["Solo B"].iter_rows(min_row=2, values_only=True)) == [
        ("202B3", "555PN", solo_b)
    ]
    workbook.close()
