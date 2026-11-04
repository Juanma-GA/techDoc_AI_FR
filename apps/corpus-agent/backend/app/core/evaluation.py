"""Deterministic scoring helpers for versioned Corpus Agent benchmarks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any


def _finding_key(finding: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(finding.get("source_id") or ""),
        str(finding.get("category") or "").strip().casefold(),
    )


def _metrics(
    tp: int,
    fp: int,
    fn: int,
    supported: int,
    predictions: int,
    severity_correct: int,
    evidence_exact: int,
) -> dict[str, int | float]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "evidence_supported": supported,
        "evidence_unsupported": predictions - supported,
        "evidence_support_rate": supported / predictions if predictions else 1.0,
        "severity_correct": severity_correct,
        "severity_accuracy": (
            severity_correct / tp if tp else (1.0 if fn == 0 else 0.0)
        ),
        "evidence_exact": evidence_exact,
        "evidence_exact_rate": evidence_exact / tp if tp else (1.0 if fn == 0 else 0.0),
    }


def score_scenario(
    scenario: Mapping[str, Any],
    predictions: Sequence[Mapping[str, Any]],
    *,
    abstained: bool = False,
) -> dict[str, int | float | bool | str]:
    """Score findings, exact source evidence, and expected abstention for one case."""
    expected = scenario.get("expected_findings", [])
    documents = {
        str(document.get("id") or ""): str(document.get("text") or "")
        for document in scenario.get("documents", [])
    }

    unmatched_predictions = set(range(len(predictions)))
    tp = 0
    severity_correct = 0
    evidence_exact = 0
    for expected_finding in expected:
        key = _finding_key(expected_finding)
        match = next(
            (
                index
                for index in unmatched_predictions
                if _finding_key(predictions[index]) == key
            ),
            None,
        )
        if match is not None:
            unmatched_predictions.remove(match)
            tp += 1
            actual = predictions[match]
            severity_correct += int(
                str(actual.get("severity") or "").casefold()
                == str(expected_finding.get("severity") or "").casefold()
            )
            evidence_exact += int(
                str(actual.get("evidence") or "")
                == str(expected_finding.get("evidence") or "")
            )

    supported = sum(
        1
        for finding in predictions
        if (evidence := str(finding.get("evidence") or ""))
        and evidence in documents.get(str(finding.get("source_id") or ""), "")
    )
    fp = len(predictions) - tp
    fn = len(expected) - tp
    expected_abstention = bool(scenario.get("expected_abstention", False))
    result: dict[str, int | float | bool | str] = {
        "scenario_id": str(scenario.get("id") or ""),
        "domain": str(scenario.get("domain") or ""),
        "abstention_expected": expected_abstention,
        "abstained": abstained,
        "abstention_correct": expected_abstention == abstained,
    }
    result.update(
        _metrics(
            tp,
            fp,
            fn,
            supported,
            len(predictions),
            severity_correct,
            evidence_exact,
        )
    )
    return result


def score_dataset(
    scenarios: Sequence[Mapping[str, Any]],
    predictions_by_scenario: Mapping[str, Mapping[str, Any]],
    *,
    dataset_version: str = "unspecified",
    run_metadata: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return micro-averaged metrics overall and separately for each domain."""
    scored: list[dict[str, int | float | bool | str]] = []
    for scenario in scenarios:
        prediction = predictions_by_scenario.get(str(scenario.get("id") or ""), {})
        findings = prediction.get("findings", [])
        scored.append(
            score_scenario(
                scenario,
                findings,
                abstained=bool(prediction.get("abstained", False)),
            )
        )

    by_domain: dict[str, list[dict[str, int | float | bool | str]]] = defaultdict(list)
    for item in scored:
        by_domain[str(item["domain"])].append(item)

    def aggregate(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        totals = {
            key: sum(int(item[key]) for item in items)
            for key in (
                "true_positives",
                "false_positives",
                "false_negatives",
                "evidence_supported",
                "evidence_unsupported",
                "severity_correct",
                "evidence_exact",
            )
        }
        metrics = _metrics(
            totals["true_positives"],
            totals["false_positives"],
            totals["false_negatives"],
            totals["evidence_supported"],
            totals["evidence_supported"] + totals["evidence_unsupported"],
            totals["severity_correct"],
            totals["evidence_exact"],
        )
        return {
            "scenario_count": len(items),
            **metrics,
            "abstention_accuracy": (
                sum(bool(item["abstention_correct"]) for item in items) / len(items)
                if items else 1.0
            ),
            "abstentions_expected": sum(bool(item["abstention_expected"]) for item in items),
            "correct_abstentions": sum(
                bool(item["abstention_expected"]) and bool(item["abstained"])
                for item in items
            ),
            "abstentions_missed": sum(
                bool(item["abstention_expected"]) and not bool(item["abstained"])
                for item in items
            ),
            "unexpected_abstentions": sum(
                not bool(item["abstention_expected"]) and bool(item["abstained"])
                for item in items
            ),
        }

    return {
        "dataset_version": dataset_version,
        "run_metadata": dict(run_metadata or {}),
        "overall": aggregate(scored),
        "domains": {domain: aggregate(items) for domain, items in sorted(by_domain.items())},
        "scenarios": scored,
    }
