"""Pipeline FTM déterministe sur les fixtures committées (`tests/fixtures/`).

Verrouille deux choses, par famille de règle :
- `fiche_conforme.xlsm`     -> AUCUNE anomalie déterministe ;
- `fiche_non_conforme.xlsm` -> exactement l'ensemble `EXPECTED_TYPES`
  (une anomalie au moins par check déterministe).

Si ce test casse après une évolution des règles, régénérer les fixtures
(`python tests/fixtures/build_fixtures.py`) et ajuster `EXPECTED_TYPES` /
le contenu des fiches dans `tests/fixtures/build_fixtures.py`.

Les checks IA (orthographe, conformité visuelle, règles personnalisées) et à
référentiel (granule, cross-checks BASL) sont inertes ici (ni Mistral ni
référentiel attaché) — couverts par ailleurs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.checks.custom_rules import run_custom_rules
from app.checks.granule import run_granule
from app.checks.illustration import run_illustration
from app.checks.operations import run_operations
from app.checks.referentiel_items import run_referentiel_items
from app.checks.script import run_script
from app.checks.text_rules import run_text_rules
from app.core.rules import reset_rules
from app.db.models import AnalysisRun, File, FileVersion, Project
from app.db.session import Base, SessionLocal, engine
from app.parsers import parse_any

from tests.fixtures.build_fixtures import EXPECTED_TYPES

_FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Pipeline déterministe complet (granule / custom inertes sans ref / Mistral).
_CHECKS = (
    run_script, run_granule, run_text_rules, run_operations,
    run_referentiel_items, run_illustration, run_custom_rules,
)


@pytest.fixture(scope="module", autouse=True)
def _setup_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def _reset_rules_after_test():
    yield
    reset_rules()


def _analyse(fixture_name: str) -> set[str]:
    """Joue le pipeline déterministe sur une fixture et renvoie l'ensemble des
    types d'anomalies émis. `storage_path` pointe le vrai fichier (les checks
    colonne-par-lettre / illustration relisent le xlsm)."""
    path = _FIXTURES / fixture_name
    assert path.is_file(), f"fixture manquante : {path}"
    db: Session = SessionLocal()
    try:
        project = Project(name=f"Fx-{uuid.uuid4().hex[:8]}", description="",
                          vision_enabled=False)
        db.add(project)
        db.flush()
        f = File(project_id=project.id, current_name=fixture_name, mime_type="x")
        db.add(f)
        db.flush()
        text = parse_any(str(path))["text"]
        db.add(FileVersion(
            file_id=f.id, filename=fixture_name, storage_path=str(path),
            sha256="0" * 64, size=len(text), extracted_text=text,
            uploaded_at=datetime.now(timezone.utc),
        ))
        run = AnalysisRun(project_id=project.id, status="running")
        db.add(run)
        db.flush()
        db.refresh(project)
        types: set[str] = set()
        for check in _CHECKS:
            for a in check(db, project, run.id):
                types.add(a.type)
        return types
    finally:
        db.rollback()
        db.close()


def test_fiche_conforme_emits_no_anomaly() -> None:
    assert _analyse("fiche_conforme.xlsx") == set()


def test_fiche_non_conforme_covers_every_rule_family() -> None:
    detected = _analyse("fiche_non_conforme.xlsx")
    missing = EXPECTED_TYPES - detected
    assert not missing, f"familles non couvertes par la fiche : {sorted(missing)}"
    extra = detected - EXPECTED_TYPES
    assert not extra, f"types inattendus (mettre à jour EXPECTED_TYPES ?) : {sorted(extra)}"
