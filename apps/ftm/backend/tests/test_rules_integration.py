"""Tests d'intégration du moteur de règles FTM Agent v4.

Couvre les checks déterministes (sans appel Mistral, sans référentiel) :
script, texte général, opérations, illustrations, items du référentiel.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.checks.custom_rules import run_custom_rules
from app.checks.illustration import run_illustration
from app.checks.operations import run_operations
from app.checks.referentiel_items import run_referentiel_items
from app.checks.script import run_script
from app.checks.text_rules import run_text_rules
from app.core.rules import reset_rules, save_rules
from app.db.models import AnalysisRun, File, FileVersion, Project
from app.db.session import Base, SessionLocal, engine


@pytest.fixture(scope="module", autouse=True)
def _setup_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def db() -> Session:
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(autouse=True)
def _reset_rules_after_test():
    yield
    reset_rules()


def _make_project_with_file(
    db: Session, filename: str, text: str = ""
) -> tuple[Project, AnalysisRun]:
    project = Project(name=f"Proj-{uuid.uuid4().hex[:8]}", description="", vision_enabled=False)
    db.add(project)
    db.flush()
    f = File(project_id=project.id, current_name=filename, mime_type="text/plain")
    db.add(f)
    db.flush()
    v = FileVersion(
        file_id=f.id,
        filename=filename,
        storage_path="<dummy>",
        sha256="0" * 64,
        size=len(text),
        extracted_text=text,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(v)
    run = AnalysisRun(project_id=project.id, status="running")
    db.add(run)
    db.flush()
    return project, run


# --------------------------- script ---------------------------------------

def test_script_flags_wrong_format(db: Session) -> None:
    project, run = _make_project_with_file(db, "ftm.xlsm", "Script : DMC-TG3-1234 ...")
    anomalies = run_script(db, project, run.id)
    assert any(a.type == "script" for a in anomalies), \
        "Un script qui ne commence pas par DMC-TG5- doit être signalé"


def test_script_toggle_disables_check(db: Session) -> None:
    """Désactiver `script.format` via _rule_state → aucune anomalie script
    même sur un livrable non conforme. Valide le toggle E2E."""
    save_rules({"_rule_state": {"script.format": {"enabled": False}}})
    project, run = _make_project_with_file(db, "ftm.xlsm", "Script : BAD-XX")
    anomalies = run_script(db, project, run.id)
    assert all(a.type != "script" for a in anomalies), \
        "Quand script.format est désactivée, aucune anomalie script ne doit être émise"


def test_serrage_native_toggle_disables_check(db: Session) -> None:
    """Désactiver `serrage.marquage_ecrimetal` via la clé native legacy."""
    save_rules({"serrage": {"marquage_ecrimetal_obligatoire": False}})
    project, run = _make_project_with_file(db, "ftm.xlsm",
                                           "Serrer la vis au couple de 12 N.m sur le support.")
    anomalies = run_operations(db, project, run.id)
    assert all("écrimétal" not in (a.message or "").lower() for a in anomalies), \
        "Toggle natif marquage_ecrimetal_obligatoire=false → pas d'anomalie écrimétal"


def test_script_passes_conformant(db: Session) -> None:
    project, run = _make_project_with_file(db, "ftm.xlsm", "Script : DMC-TG5-AB12 du jour.")
    anomalies = run_script(db, project, run.id)
    assert anomalies == [], "Un script DMC-TG5-AAAA conforme ne doit rien signaler"


# --------------------------- texte général --------------------------------

def test_text_flags_leading_space_and_missing_period(db: Session) -> None:
    text = "[ONGLET: Tâche de maintenance]\n Déposer la vis de fixation du carter"
    project, run = _make_project_with_file(db, "ftm.xlsm", text)
    anomalies = run_text_rules(db, project, run.id)
    msgs = [a.message for a in anomalies]
    assert any("espace en début" in m.lower() for m in msgs)
    assert any("point" in m.lower() for m in msgs)


def test_text_flags_non_verb_sentence_start(db: Session) -> None:
    text = "[ONGLET: Tâche de maintenance]\nLe carter doit être déposé avec précaution."
    project, run = _make_project_with_file(db, "ftm.xlsm", text)
    anomalies = run_text_rules(db, project, run.id)
    assert any("début de phrase" in a.message.lower() for a in anomalies)


def test_text_flags_ordre_taches_gap(db: Session) -> None:
    text = (
        "[ONGLET: Tâche de maintenance]\n"
        "Ordre des tâches | Opération\n"
        "1 | Déposer le carter avec précaution.\n"
        "2 | Contrôler visuellement la pièce déposée.\n"
        "5 | Reposer le carter avec précaution.\n"
    )
    project, run = _make_project_with_file(db, "ftm.xlsm", text)
    anomalies = run_text_rules(db, project, run.id)
    assert any(a.type == "ordre_taches" for a in anomalies), \
        "Un saut de numéro (2 → 5) doit être signalé"


# --------------------------- opérations -----------------------------------

def test_operations_flags_torque_without_ecrimetal(db: Session) -> None:
    text = "Serrer la vis de fixation au couple de 12 N.m sur le support."
    project, run = _make_project_with_file(db, "ftm.xlsm", text)
    anomalies = run_operations(db, project, run.id)
    assert any(a.type == "serrage" for a in anomalies), \
        "Un couple de serrage sans écrimétal doit être signalé"


def test_operations_flags_missing_counter_action(db: Session) -> None:
    text = "Consigner électriquement la rame avant toute intervention."
    project, run = _make_project_with_file(db, "ftm.xlsm", text)
    anomalies = run_operations(db, project, run.id)
    assert any(a.type == "complementaire" and "Déconsigner" in a.suggestion
               for a in anomalies), \
        "Une consignation sans déconsignation complémentaire doit être signalée"


# --------------------------- illustrations ---------------------------------

def test_illustration_flags_non_canonical_reperage(db: Session) -> None:
    text = "Voir le repère Rep 12 sur le schéma de montage du carter."
    project, run = _make_project_with_file(db, "ftm.xlsm", text)
    anomalies = run_illustration(db, project, run.id)
    assert any(a.type == "illustration" for a in anomalies), \
        "Un repérage hors format RepXX(FigZZ) doit être signalé"


# --------------------------- référentiel (structurel) ----------------------

def test_referentiel_flags_duplicate_rechange(db: Session) -> None:
    text = (
        "[ONGLET: Récapitulatif]\n"
        "Rechange | Quantité\n"
        "Joint torique 12mm | 2\n"
        "Joint torique 12mm | 1\n"
    )
    project, run = _make_project_with_file(db, "ftm.xlsm", text)
    anomalies = run_referentiel_items(db, project, run.id)
    assert any(a.type == "rechange" and "doublon" in a.message.lower()
               for a in anomalies), \
        "Un rechange en doublon doit être signalé"


# --------------------------- règles personnalisées (IA) -------------------

class _FakeMistral:
    """Stub de MistralClient : `chat_json` renvoie un payload figé."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def chat_json(self, messages: list[dict]) -> dict:
        return self._payload


def test_custom_rules_skipped_without_mistral(db: Session) -> None:
    save_rules({"regles_personnalisees": [
        {"id": "cr1", "label": "Test", "consigne": "Pas de juron.", "severity": "high"},
    ]})
    project, run = _make_project_with_file(db, "ftm.xlsm", "Déposer le carter.")
    anomalies = run_custom_rules(db, project, run.id, mistral=None)
    assert anomalies == [], "Sans Mistral, le check de règles personnalisées est inactif"


def test_custom_rules_emit_with_mistral(db: Session) -> None:
    save_rules({"regles_personnalisees": [
        {"id": "cr1", "label": "Majuscules", "consigne": "Pas de mot tout en majuscules.",
         "severity": "high"},
    ]})
    project, run = _make_project_with_file(db, "ftm.xlsm", "DEPOSER le carter.")
    fake = _FakeMistral({"anomalies": [
        {"regle_id": "cr1", "message": "mot en majuscules", "suggestion": "Corriger.",
         "extrait": "DEPOSER"},
    ]})
    anomalies = run_custom_rules(db, project, run.id, mistral=fake)
    assert len(anomalies) == 1
    assert anomalies[0].type == "personnalisee"
    assert anomalies[0].severity == "high"
    assert "Majuscules" in anomalies[0].message
