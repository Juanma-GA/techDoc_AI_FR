from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.evaluation import score_dataset, score_scenario

_BENCHMARK_PATH = Path(__file__).parent / "fixtures" / "evaluation" / "benchmark-v1.json"


def _scenarios() -> list[dict[str, Any]]:
    benchmark = json.loads(_BENCHMARK_PATH.read_text(encoding="utf-8"))
    return [
        {"domain": pack["domain"], **scenario}
        for pack in benchmark["domain_packs"]
        for scenario in pack["scenarios"]
    ]


def test_benchmark_covers_the_initial_domain_packs() -> None:
    scenarios = _scenarios()

    assert {scenario["domain"] for scenario in scenarios} == {
        "ged",
        "technical-documentation",
        "testability",
        "industrial-maintenance",
    }
    assert len(scenarios) >= 8
    for scenario in scenarios:
        for finding in scenario["expected_findings"]:
            source = next(
                document["text"]
                for document in scenario["documents"]
                if document["id"] == finding["source_id"]
            )
            assert finding["evidence"] in source


def test_score_scenario_matches_findings_and_verifies_evidence() -> None:
    scenario = _scenarios()[0]
    finding = scenario["expected_findings"][0]

    result = score_scenario(scenario, [finding])

    assert result["true_positives"] == 1
    assert result["false_positives"] == 0
    assert result["false_negatives"] == 0
    assert result["precision"] == 1
    assert result["recall"] == 1
    assert result["evidence_support_rate"] == 1
    assert result["severity_correct"] == 1
    assert result["evidence_exact_rate"] == 1


def test_score_scenario_counts_unsupported_and_duplicate_findings() -> None:
    scenario = _scenarios()[0]
    finding = scenario["expected_findings"][0]
    duplicate = {**finding, "evidence": "Text absent from the source"}

    result = score_scenario(scenario, [finding, duplicate])

    assert result["true_positives"] == 1
    assert result["false_positives"] == 1
    assert result["evidence_unsupported"] == 1
    assert result["evidence_support_rate"] == 0.5


def test_score_scenario_flags_wrong_severity_and_nonmatching_quote() -> None:
    scenario = _scenarios()[0]
    finding = scenario["expected_findings"][0]
    prediction = {**finding, "severity": "low", "evidence": "Owner: Quality"}

    result = score_scenario(scenario, [prediction])

    assert result["true_positives"] == 1
    assert result["severity_correct"] == 0
    assert result["evidence_exact"] == 0


def test_score_dataset_reports_each_domain_separately() -> None:
    scenarios = _scenarios()
    report = score_dataset(
        scenarios,
        {},
        dataset_version="1.0",
        run_metadata={"model": "synthetic-model", "prompt_version": "test-v1"},
    )

    assert report["dataset_version"] == "1.0"
    assert report["run_metadata"]["model"] == "synthetic-model"
    assert report["overall"]["scenario_count"] == len(scenarios)
    assert report["overall"]["false_negatives"] > 0
    assert report["overall"]["abstention_accuracy"] == 1 - (
        report["overall"]["abstentions_expected"] / len(scenarios)
    )
    assert report["overall"]["correct_abstentions"] == 0
    assert set(report["domains"]) == {scenario["domain"] for scenario in scenarios}


def test_expected_abstention_is_scored_explicitly() -> None:
    scenario = next(s for s in _scenarios() if s.get("expected_abstention"))

    correct = score_scenario(scenario, [], abstained=True)
    incorrect = score_scenario(scenario, [], abstained=False)

    assert correct["abstention_correct"] is True
    assert incorrect["abstention_correct"] is False
