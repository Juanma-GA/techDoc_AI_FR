from __future__ import annotations

import json
import uuid

from openpyxl import Workbook

from app.checks.cross_reference import run_reference_cross_checks
from app.config import settings
from app.core.demo_seed import _SHEETS, _build_workbook, _seed_demo_sources
from app.db.models import File, FileVersion, Project
from app.parsers import parse_any


class _Collector:
    def __init__(self) -> None:
        self.items = []

    def add(self, item) -> None:
        self.items.append(item)


def _workbook(path, sheet: str, values: list[str]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet
    for value in values:
        worksheet.append([value])
    workbook.save(path)


def test_cross_check_uses_mapped_sources_and_reports_missing_references(tmp_path) -> None:
    reference_path = tmp_path / "reference.xlsx"
    basl_path = tmp_path / "basl.xlsx"
    _workbook(reference_path, "Catalogue", ["Référence", "PN-DEMO-1"])
    _workbook(basl_path, "Outillage", ["Référence", "TL-1001"])

    project_id = uuid.uuid4()
    file_id = uuid.uuid4()
    version_id = uuid.uuid4()
    version = FileVersion(
        id=version_id,
        file_id=file_id,
        filename="maintenance.xlsx",
        storage_path="",
        sha256="synthetic",
        extracted_text=(
            "[ONGLET: Taches]\n"
            "1 | Remplacer | Utiliser PN-DEMO-1 et TL-1001\n"
            "2 | Controler | Verifier TL-9999"
        ),
    )
    file = File(
        id=file_id,
        project_id=project_id,
        current_name=version.filename,
        versions=[version],
    )
    project = Project(
        id=project_id,
        name="Synthetic project",
        reference_path=str(reference_path),
        basl_path=str(basl_path),
        reference_columns=json.dumps([
            {"name": "spare_parts", "sheet": "Catalogue", "column": "A"},
        ]),
        basl_columns=json.dumps([
            {"name": "outillage", "sheet": "Outillage", "column": "A"},
        ]),
        files=[file],
    )
    collector = _Collector()

    anomalies = run_reference_cross_checks(
        collector, project, uuid.uuid4(), only_file_ids={file_id}
    )

    assert anomalies == collector.items
    assert len(anomalies) == 1
    assert anomalies[0].type == "reference_cross_check"
    assert anomalies[0].evidence == "TL-9999"
    assert anomalies[0].file_version_id == version_id


def test_demo_sources_reproduce_a_missing_reference_finding(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    project_id = uuid.uuid4()
    project = Project(id=project_id, name="Synthetic demo project")
    _seed_demo_sources(project)

    document_path = tmp_path / "maintenance.xlsx"
    document_path.write_bytes(_build_workbook(_SHEETS[1]))
    extracted_text = parse_any(str(document_path))["text"]
    file_id = uuid.uuid4()
    version_id = uuid.uuid4()
    version = FileVersion(
        id=version_id,
        file_id=file_id,
        filename=document_path.name,
        storage_path=str(document_path),
        sha256="synthetic",
        extracted_text=extracted_text,
    )
    file = File(
        id=file_id,
        project_id=project_id,
        current_name=document_path.name,
        versions=[version],
    )
    project.files = [file]
    collector = _Collector()

    anomalies = run_reference_cross_checks(
        collector, project, uuid.uuid4(), only_file_ids={file_id}
    )

    assert [anomaly.evidence for anomaly in anomalies] == ["TL-9999"]
