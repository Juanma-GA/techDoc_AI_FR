"""Structured content loading and validation for one-pager generation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON '{path}': {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def bilingual_content(content: dict[str, Any]) -> dict[str, dict[str, str]]:
    languages = {}
    for language in ("fr", "en"):
        value = content.get(language)
        if not isinstance(value, dict):
            raise ValueError(f"'{language}' must be a content object")
        languages[language] = content_values(value)
    return languages


def content_values(content: dict[str, Any]) -> dict[str, str]:
    required = [
        "main_title", "section_title", "application_name", "status",
        "challenge", "solution", "features", "callouts", "security",
    ]
    missing = [key for key in required if key not in content]
    if missing:
        raise ValueError(f"Missing content fields: {', '.join(missing)}")

    features = content["features"]
    callouts = content["callouts"]
    security = content["security"]
    if not isinstance(features, list) or not 3 <= len(features) <= 5:
        raise ValueError("'features' must contain 3 to 5 strings")
    if not all(isinstance(item, str) and item.strip() for item in features):
        raise ValueError("Every feature must be a non-empty string")
    if not isinstance(callouts, list) or len(callouts) != 3:
        raise ValueError("'callouts' must contain exactly 3 strings")
    if not all(isinstance(item, str) and item.strip() for item in callouts):
        raise ValueError("Every callout must be a non-empty string")
    if not isinstance(security, dict):
        raise ValueError("'security' must be an object")
    for key in ("local", "shared"):
        if not isinstance(security.get(key), str) or not security[key].strip():
            raise ValueError(f"'security.{key}' must be a non-empty string")

    text_keys = (
        "main_title", "section_title", "application_name", "status",
        "challenge", "solution",
    )
    if any(not isinstance(content[key], str) or not content[key].strip() for key in text_keys):
        raise ValueError("Required text fields must be non-empty strings")
    values = {key: content[key].strip() for key in text_keys}
    values.update({
        "features": "\n".join(item.strip() for item in features),
        "callout_1": callouts[0].strip(),
        "callout_2": callouts[1].strip(),
        "callout_3": callouts[2].strip(),
        "local_security": security["local"].strip(),
        "shared_security": security["shared"].strip(),
        "footnote": str(content.get("footnote", "")).strip(),
    })
    return values
