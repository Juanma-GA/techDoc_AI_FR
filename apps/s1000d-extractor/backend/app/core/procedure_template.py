"""Transfer unambiguous human tag mappings from the first procedure."""

from __future__ import annotations

from typing import Any

from app.core.procedure_tags import build_template, template_key, valid_target_tag

ReviewData = dict[str, Any]


def apply_template(
    source_review: ReviewData,
    target_review: ReviewData,
    *,
    source_dm_id: str,
    saved_at: str,
) -> int:
    choices = build_template(source_review["passages"])
    applied = 0
    for passage in target_review["passages"]:
        key = template_key(passage)
        if (
            key is None or passage.get("role", "content") != "content"
            or passage.get("decision") is not None
        ):
            continue
        choice = choices.get(key)
        if choice is None:
            continue
        destination, tag = choice
        if not valid_target_tag(destination, tag, passage):
            continue
        passage["decision"] = destination
        passage["target_tag"] = tag
        passage["template_source_dm_id"] = source_dm_id
        applied += 1

    if applied:
        target_review["template_source_dm_id"] = source_dm_id
        target_review["saved_at"] = saved_at
        complete = all(
            passage.get("role", "content") != "content"
            or valid_target_tag(passage.get("decision"), passage.get("target_tag"), passage)
            for passage in target_review["passages"]
        )
        target_review["status"] = "reviewed" if complete else "pending"
        target_review["partial"] = not complete
    return applied


def clear_template_applications(state: ReviewData, source_dm_id: str) -> None:
    for dm_id, review in state.get("reviews", {}).items():
        if dm_id == source_dm_id:
            continue
        changed = False
        for passage in review.get("passages", []):
            if passage.get("template_source_dm_id") != source_dm_id:
                continue
            passage["decision"] = None
            passage["target_tag"] = None
            passage.pop("template_source_dm_id", None)
            changed = True
        if not changed:
            continue
        review["template_source_dm_id"] = None
        if review.get("status") != "stale":
            review["status"] = "pending"
            review["partial"] = any(
                passage.get("decision") is not None
                for passage in review.get("passages", [])
                if passage.get("role", "content") == "content"
            )
