"""Tests unitaires de l'orchestration multi-nomenclatures."""

from __future__ import annotations

import uuid

import pytest

from app.core.nomenclature_diff import build_matrix, comparison_pairs


def _ids(count: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(count)]


def test_two_versions_keep_historical_pair() -> None:
    run_ids = _ids(2)

    assert comparison_pairs(run_ids, mode="chronology") == [(run_ids[0], run_ids[1])]
    assert comparison_pairs(run_ids, mode="reference", reference_run_id=run_ids[0]) == [
        (run_ids[0], run_ids[1])
    ]


def test_chronology_compares_adjacent_versions() -> None:
    run_ids = _ids(4)

    assert comparison_pairs(run_ids, mode="chronology") == [
        (run_ids[0], run_ids[1]),
        (run_ids[1], run_ids[2]),
        (run_ids[2], run_ids[3]),
    ]


def test_reference_compares_every_version_to_selected_reference() -> None:
    run_ids = _ids(4)

    assert comparison_pairs(run_ids, mode="reference", reference_run_id=run_ids[1]) == [
        (run_ids[1], run_ids[0]),
        (run_ids[1], run_ids[2]),
        (run_ids[1], run_ids[3]),
    ]


def test_pairs_reject_duplicates_and_external_reference() -> None:
    run_ids = _ids(2)

    with pytest.raises(ValueError, match="qu'une fois"):
        comparison_pairs([run_ids[0], run_ids[0]], mode="chronology")
    with pytest.raises(ValueError, match="reference"):
        comparison_pairs(run_ids, mode="reference", reference_run_id=uuid.uuid4())


def test_matrix_has_one_cell_per_version_and_marks_changes() -> None:
    run_ids = _ids(3)
    items = {
        run_ids[0]: [{"sin": "SIN-1", "catpart": "P1"}, {"sin": "SIN-2", "catpart": "P2"}],
        run_ids[1]: [{"sin": "SIN-1", "catpart": "P1B"}, {"sin": "SIN-3", "catpart": "P3"}],
        run_ids[2]: [{"sin": "SIN-1", "catpart": "P1B"}, {"sin": "SIN-3", "catpart": "P3"}],
    }
    comparisons = []
    for base_id, other_id in comparison_pairs(run_ids, mode="chronology"):
        comparisons.append(
            {
                "base_run_id": base_id,
                "other_run_id": other_id,
                "diff": {
                    "added_sin": [{"sin": "SIN-3"}] if other_id == run_ids[1] else [],
                    "removed_sin": [{"sin": "SIN-2"}] if other_id == run_ids[1] else [],
                    "changed_pn": [{"sin": "SIN-1"}] if other_id == run_ids[1] else [],
                },
            }
        )

    matrix = build_matrix(run_ids, items, comparisons, mode="chronology")
    by_sin = {row["sin"]: row for row in matrix}

    assert len(by_sin["SIN-1"]["cells"]) == 3
    assert [cell["pn"] for cell in by_sin["SIN-1"]["cells"]] == ["P1", "P1B", "P1B"]
    assert by_sin["SIN-1"]["cells"][1]["state"] == "changed"
    assert by_sin["SIN-2"]["cells"][1] == {
        "run_id": run_ids[1],
        "present": False,
        "pn": "",
        "state": "removed",
    }
    assert by_sin["SIN-3"]["cells"][1]["state"] == "added"
