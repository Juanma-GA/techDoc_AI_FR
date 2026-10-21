"""Build the public per-DM projection returned by the migration wizard."""

from __future__ import annotations

from typing import Any

from app.core import wizard_split as ws

_BREX_PROFILE_RULES = {
    "BREX",
    "BREX_VALUE",
    "BREX_VALUE_UNSUPPORTED",
    "BREX_CONTEXT_UNVERIFIABLE",
    "BREX_PATH_UNVERIFIABLE",
    "BREX_FLAG_UNSUPPORTED",
    "BREX_UNSUPPORTED",
}


def project_dm_state(dm: dict[str, Any], step: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "dm_id": dm["dm_id"],
        "dmc": dm.get("dmc", ""),
        "title": dm["title"],
        "dm_type": dm["dm_type"],
        "is_orphan": bool(dm.get("is_orphan")),
        "node_count": ws.node_count(dm["tree"]),
    }
    if step == "split":
        entry["preview"] = ws.dm_preview(dm["tree"])
    if step == "structure":
        entry["tree"] = dm["tree"]
    if step == "generate":
        violations = dm.get("violations") or []
        entry["violation_count"] = len(violations)
        entry["has_xml"] = bool(dm.get("xml"))
        entry["missing_fields"] = dm.get("missing_fields") or []
        entry["xsd_valid"] = dm.get("xsd_valid") is True
        entry["xsd_violations"] = [
            violation for violation in violations
            if violation.get("rule") in {"XSD", "WELLFORMED"}
        ]
        entry["brex_violations"] = [
            violation for violation in violations
            if violation.get("rule") in _BREX_PROFILE_RULES
        ]
        entry["cir_unresolved"] = dm.get("cir_unresolved") or []
    return entry
