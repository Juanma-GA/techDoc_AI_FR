"""Deterministic cross-checks between document references and project catalogues."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.checks.custom_rules import RuleEvaluationStats
from app.checks.ftm_doc import latest_version, make_anomaly
from app.core.mistral_client import MistralClient
from app.core.rules import basl_columns_for, reference_columns_for
from app.db.models import Anomaly, Project
from app.parsers.reference import reference_column_values

_REFERENCE_RE = re.compile(r"\b(?:TL-\d{3,}|PN-[A-Z0-9]+(?:-[A-Z0-9]+)*)\b", re.IGNORECASE)


def _catalogue_values(path: str | None, mappings: list[dict]) -> set[str]:
    if not path or not Path(path).is_file():
        return set()
    values: set[str] = set()
    for mapping in mappings:
        column = str(mapping.get("column") or "").strip()
        if not column:
            continue
        values.update(
            value.strip().upper()
            for value in reference_column_values(
                path,
                str(mapping.get("sheet") or ""),
                column,
            )
            if value.strip()
        )
    return values


def run_reference_cross_checks(
    db: Session,
    project: Project,
    run_id: uuid.UUID,
    mistral: MistralClient | None = None,
    *,
    only_file_ids: set[uuid.UUID] | None = None,
    stats: RuleEvaluationStats | None = None,
) -> list[Anomaly]:
    """Flag tool and spare-part references absent from both project catalogues."""
    catalogues = _catalogue_values(
        project.basl_path, basl_columns_for(project)
    ) | _catalogue_values(project.reference_path, reference_columns_for(project))
    if not catalogues:
        return []

    anomalies: list[Anomaly] = []
    for file in project.files:
        if only_file_ids is not None and file.id not in only_file_ids:
            continue
        version = latest_version(file)
        if version is None:
            continue
        for token in sorted(set(_REFERENCE_RE.findall(version.extracted_text or ""))):
            if token.upper() in catalogues:
                continue
            anomaly = make_anomaly(
                project,
                version,
                run_id,
                "reference_cross_check",
                "medium",
                f"La référence {token} est absente des colonnes mappées du référentiel et de la BASL.",
                f"Vérifier la référence {token} dans les sources de référence.",
                f"{version.filename} | référence {token}",
                category="Référentiel / BASL",
                evidence=token,
            )
            db.add(anomaly)
            anomalies.append(anomaly)
    return anomalies
