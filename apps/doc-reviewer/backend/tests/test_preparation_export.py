from __future__ import annotations

import json
import uuid
from collections.abc import Iterator

import fitz
import pytest
from fastapi.testclient import TestClient

from app.core.pdf_annotate import RevisionPlanSection, build_commented_pdf
from app.core.preparation_export import PreparationExport, build_preparation_export
from app.core.preparation_state import get_record
from app.db.models import Document, Suggestion
from app.db.session import SessionLocal


@pytest.fixture
def prepared_id(client: TestClient) -> Iterator[uuid.UUID]:
    with fitz.open() as pdf:
        for index in range(5):
            page = pdf.new_page()
            page.insert_text((50, 100), f"Synthetic preparation page {index + 1}")
        uploaded = client.post(
            "/api/v1/documents?target=imperial",
            files={"file": ("synthetic.pdf", pdf.tobytes(), "application/pdf")},
        )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uuid.UUID(uploaded.json()["id"])
    initialized = client.get(f"/api/v1/documents/{document_id}/preparation")
    assert initialized.status_code == 200, initialized.text
    with SessionLocal() as db:
        record = get_record(db, document_id)
        assert record is not None
        record.preparation_mapping_json = json.dumps({
            "meta_revision_date": "AUG 03/26",
            "meta_revision_number": "04",
        })
        record.page_decisions_json = json.dumps([
            {
                "page": 1, "page_type": "TP1", "document_page": "TP 1",
                "is_modified": True, "manual_override": True, "failures": [],
            },
            {
                "page": 2, "page_type": "LEP", "document_page": "LEP 1",
                "is_modified": False, "failures": [],
            },
            {
                "page": 3, "page_type": "ROR", "document_page": "ROR 1",
                "is_modified": True,
                "failures": [{
                    "rule_id": "CUSTOM_PREP_ROR_NEW_ROW",
                    "title": "Nouvelle ligne ROR",
                    "message": "Ligne manquante",
                }],
            },
            {
                "page": 4, "page_type": "HIGHLIGHTS", "document_page": "HIGHLIGHTS 1",
                "is_modified": True,
                "failures": [{
                    "rule_id": "CUSTOM_PREP_HIGHLIGHTS_REVISION_DATE",
                    "title": "Date Highlights",
                    "message": "Date incorrecte",
                }],
            },
            {
                "page": 5, "page_type": "INTRODUCTION", "document_page": "INTRO 1",
                "is_modified": False, "failures": [],
            },
        ])
        db.commit()
    yield document_id


def _export(client: TestClient, document_id: uuid.UUID) -> PreparationExport:
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        assert document is not None
        return build_preparation_export(document, db, client.app.state.client_configuration)


def _section(export: PreparationExport, title: str) -> str:
    return "\n".join(
        line for section in export.revision_sections
        if section.title.startswith(title)
        for line in section.lines
    )


def test_selected_pages_export_without_missing_pages_or_annotations(
    client: TestClient, prepared_id: uuid.UUID,
) -> None:
    export = _export(client, prepared_id)

    assert export.missing_pages == ()
    pages = _section(export, "Pages à modifier")
    assert "Page PDF 1 | TP1 | Référence documentaire : TP 1" in pages
    assert "Page PDF 3" in pages
    assert "Page PDF 4" in pages
    assert "Page PDF 2" not in pages
    assert "Page PDF 5" not in pages
    assert "retenue manuellement" in pages
    assert "pied de page : AUG 03/26" in pages
    lep = _section(export, "LEP")
    assert "TP 1 | AUG 03/26 * (page PDF 1)" in lep
    assert "ROR 1 | AUG 03/26 * (page PDF 3)" in lep
    assert "INTRO 1 | AUG 03/26 *" not in lep
    assert "non retenue au départ" in lep
    highlights = _section(export, "Highlights")
    assert "DATED AUG 03/26" in highlights
    assert "REVISION No. 04" in highlights
    assert "pied de page Highlights : AUG 03/26" in highlights
    assert "{{" not in pages


def test_preparation_mapping_is_used_instead_of_verification(
    client: TestClient, prepared_id: uuid.UUID,
) -> None:
    saved = client.patch(
        f"/api/v1/documents/{prepared_id}",
        json={"meta_revision_date": "DEC 29/30", "meta_revision_number": "99"},
    )
    assert saved.status_code == 200, saved.text

    export = _export(client, prepared_id)
    header = _section(export, "Révision")
    assert "AUG 03/26" in header and "04" in header
    assert "DEC 29/30" not in header and "99" not in header


@pytest.mark.parametrize(("revision_date", "expected"), [
    ("JUL 14/26", "JUL 26"),
    ("JUL 15/26", "AUG 26"),
    ("DEC 15/26", "JAN 27"),
])
def test_ror_uses_existing_insertion_date_rule(
    client: TestClient, prepared_id: uuid.UUID, revision_date: str, expected: str,
) -> None:
    with SessionLocal() as db:
        record = get_record(db, prepared_id)
        assert record is not None
        record.preparation_mapping_json = json.dumps({
            "meta_revision_date": revision_date, "meta_revision_number": "04",
        })
        db.commit()

    ror = _section(_export(client, prepared_id), "Record")
    assert f"REV. No. 04 / REVISION DATE {revision_date} / INSERTION DATE {expected}" in ror


@pytest.mark.parametrize("revision_date", ["", "JUL 2026", "FEB 31/26"])
def test_missing_or_invalid_date_is_not_invented(
    client: TestClient, prepared_id: uuid.UUID, revision_date: str,
) -> None:
    with SessionLocal() as db:
        record = get_record(db, prepared_id)
        assert record is not None
        record.preparation_mapping_json = json.dumps({"meta_revision_date": revision_date})
        db.commit()

    export = _export(client, prepared_id)
    assert "À RENSEIGNER" in _section(export, "Révision")
    assert "TP 1 |" not in _section(export, "LEP")
    assert "date à confirmer" in _section(export, "LEP")
    assert "aucun mois inventé" in _section(export, "Record")


def test_unknown_reference_and_unconfirmed_decisions_are_explicit(
    client: TestClient, prepared_id: uuid.UUID,
) -> None:
    with SessionLocal() as db:
        record = get_record(db, prepared_id)
        assert record is not None
        decisions = json.loads(record.page_decisions_json)
        decisions[0]["document_page"] = None
        decisions[1]["failures"] = [{"rule_id": "CUSTOM_PREP_LEP_MODIFIED_PAGES"}]
        decisions[4]["is_modified"] = None
        record.page_decisions_json = json.dumps(decisions)
        db.commit()

    export = _export(client, prepared_id)
    assert "NON IDENTIFIÉE" in _section(export, "Pages à modifier")
    assert "Page PDF 1 : référence documentaire à identifier" in _section(export, "LEP")
    assert "- 1 | AUG" not in _section(export, "LEP")
    warnings = _section(export, "Points à confirmer")
    assert "Page PDF 2" in warnings and "arbitrage nécessaire" in warnings
    assert "Page PDF 5" in warnings and "non confirmée" in warnings


def test_correct_ror_is_not_duplicated(client: TestClient, prepared_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        record = get_record(db, prepared_id)
        assert record is not None
        decisions = json.loads(record.page_decisions_json)
        decisions[2].update(
            is_modified=False, failures=[],
            rule_results=[{"rule_id": "CUSTOM_PREP_ROR_NEW_ROW", "status": "PASS"}],
        )
        record.page_decisions_json = json.dumps(decisions)
        db.commit()

    ror = _section(_export(client, prepared_id), "Record")
    assert "ne pas la dupliquer" in ror
    assert "Ajouter ou compléter" not in ror


def test_stale_preparation_does_not_export_old_revision_plan(
    client: TestClient, prepared_id: uuid.UUID,
) -> None:
    with SessionLocal() as db:
        record = get_record(db, prepared_id)
        assert record is not None
        record.source_version = -1
        db.commit()

    export = _export(client, prepared_id)
    assert export.missing_pages == ()
    assert len(export.revision_sections) == 1
    assert export.revision_sections[0].title == "Préparation à actualiser"
    assert "AUG 03/26" not in _section(export, "Préparation")


@pytest.mark.parametrize("route", ["commented.pdf", "export?format=commented"])
def test_both_commented_routes_include_plan_but_original_and_corrected_do_not(
    client: TestClient, prepared_id: uuid.UUID, route: str,
) -> None:
    response = client.get(f"/api/v1/documents/{prepared_id}/{route}")
    assert response.status_code == 200, response.text
    with fitz.open(stream=response.content, filetype="pdf") as pdf:
        text = "\n".join(page.get_text() for page in pdf)
        assert "Pages à modifier (3)" in text
        assert "TP 1 | AUG 03/26 * (page PDF 1)" in text
        assert "INSERTION DATE AUG 26" in text
        assert "DATED AUG 03/26" in text
    for format_name in ("original", "corrected"):
        response = client.get(f"/api/v1/documents/{prepared_id}/export?format={format_name}")
        assert response.status_code == 200, response.text
        with fitz.open(stream=response.content, filetype="pdf") as pdf:
            assert pdf.page_count == 5
            assert "TP 1 | AUG 03/26 *" not in "\n".join(page.get_text() for page in pdf)


def test_long_revision_plan_is_fully_paginated(tmp_path) -> None:
    source = tmp_path / "synthetic.pdf"
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.save(source)
    lines = tuple(
        f"Page PDF {index} | Référence {index} | AUG 03/26 * " + "Consigne détaillée " * 12
        for index in range(1, 150)
    )
    content = build_commented_pdf(
        source, [], revision_sections=(RevisionPlanSection(title="Plan de révision", lines=lines),),
    )
    with fitz.open(stream=content, filetype="pdf") as pdf:
        assert pdf.page_count > 4
        text = "\n".join(page.get_text() for page in pdf)
        assert all(f"Page PDF {index} | Référence {index}" in text for index in range(1, 150))
        for page in list(pdf)[2:]:
            assert "Plan de révision" in page.get_text()
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        assert span["bbox"][0] >= 47
                        assert span["bbox"][2] <= page.rect.width - 47
                        assert span["bbox"][3] <= page.rect.height - 20


def test_long_summary_keeps_every_finding_and_existing_annotations(tmp_path) -> None:
    source = tmp_path / "synthetic.pdf"
    with fitz.open() as pdf:
        pdf.new_page()
        pdf.save(source)
    findings = [
        Suggestion(
            page=1, span_index=index, bbox="{}", rule_code=f"SYNTHETIC_{index}", severity="warning",
            message=f"Correction {index} : " + "Texte détaillé de la correction. " * 7,
            original_text="", proposed_text="",
        )
        for index in range(120)
    ]
    findings[0].bbox = json.dumps({"x0": 20, "y0": 20, "x1": 60, "y1": 40})

    content = build_commented_pdf(source, findings)

    with fitz.open(stream=content, filetype="pdf") as pdf:
        assert pdf.page_count > 3
        text = "\n".join(page.get_text() for page in pdf)
        assert all(f"SYNTHETIC_{index} -" in text for index in range(120))
        annotations = list(pdf[0].annots())
        assert len(annotations) == 1
        assert "Correction 0" in annotations[0].info["content"]


def test_changed_preparation_choices_update_the_export_without_resyncing_annotations(
    client: TestClient, prepared_id: uuid.UUID,
) -> None:
    with SessionLocal() as db:
        record = get_record(db, prepared_id)
        assert record is not None
        decisions = json.loads(record.page_decisions_json)
        decisions[0]["is_modified"] = False
        decisions[4]["is_modified"] = True
        record.page_decisions_json = json.dumps(decisions)
        db.commit()

    export = _export(client, prepared_id)
    lep = _section(export, "LEP")
    assert "TP 1 | AUG 03/26 *" not in lep
    assert "INTRO 1 | AUG 03/26 * (page PDF 5)" in lep


def test_missing_pages_and_lep_creation_impacts_are_exported_together(
    client: TestClient, prepared_id: uuid.UUID,
) -> None:
    with SessionLocal() as db:
        record = get_record(db, prepared_id)
        assert record is not None
        decisions = json.loads(record.page_decisions_json)
        decisions[2]["page_type"] = None
        decisions[2]["document_page"] = None
        record.page_decisions_json = json.dumps(decisions)
        record.absent_page_types_json = json.dumps(["ROR"])
        db.commit()

    export = _export(client, prepared_id)
    assert any("ROR" in page.page_types for page in export.missing_pages)
    assert "Page(s) à créer : ROR" in _section(export, "LEP")
    assert "AUG 03/26 *" in _section(export, "LEP")
    assert "ROR absente ou non identifiée" in _section(export, "Record")
    assert "INSERTION DATE AUG 26" in _section(export, "Record")


@pytest.mark.parametrize("conflict", ["duplicate", "classification"])
def test_ambiguous_document_references_are_not_published_as_certain_lep_entries(
    client: TestClient, prepared_id: uuid.UUID, conflict: str,
) -> None:
    with SessionLocal() as db:
        record = get_record(db, prepared_id)
        assert record is not None
        decisions = json.loads(record.page_decisions_json)
        if conflict == "duplicate":
            decisions[4]["document_page"] = "TP 1"
        else:
            decisions[0]["classification_status"] = "conflict"
        record.page_decisions_json = json.dumps(decisions)
        db.commit()

    export = _export(client, prepared_id)
    assert "TP 1 | AUG 03/26 *" not in _section(export, "LEP")
    assert "Page PDF 1 : référence documentaire à identifier" in _section(export, "LEP")
    assert "ambiguë ou classification conflictuelle : TP 1" in _section(export, "Points à confirmer")
