from __future__ import annotations

from zipfile import ZipFile

import fitz
import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.table import Table

from app.services.path_picker import BrowseKind

HEADERS = [
    "Reference",
    "Revision",
    "Subject",
    "Title",
    "Author",
    "Response required",
    "Module 3 - Open Actions",
]
PDF_TEXT = "\n".join(
    [
        "Reference: GKN-ECN-123",
        "Revision: A@2",
        "Subject: Cooling unit update",
        "Title: Replace component",
        "Author: Sample Engineer",
        "Response required: Yes",
        "Module 3 --> action ouvertes: Update drawing",
    ]
)


def _write_pdf(path, text: str) -> None:
    document = fitz.open()
    page = document.new_page()
    if text:
        page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def _write_tracker(path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "ECM Tracker"
    sheet.append(HEADERS)
    workbook.save(path)


def test_path_preferences_are_persisted(client) -> None:
    empty = client.get("/api/v1/ecm-rename/paths")

    assert empty.status_code == 200
    assert empty.json() == {"source_path": "", "tracker_path": "", "output_path": ""}

    paths = {
        "source_path": r"C:\ECM\to process",
        "tracker_path": r"C:\ECM\tracker.xlsx",
        "output_path": r"C:\ECM\processed",
    }
    saved = client.put("/api/v1/ecm-rename/paths", json=paths)
    loaded = client.get("/api/v1/ecm-rename/paths")

    assert saved.status_code == 200
    assert saved.json() == paths
    assert loaded.status_code == 200
    assert loaded.json() == paths

    changed_paths = {**paths, "output_path": r"C:\ECM\final"}
    updated = client.put("/api/v1/ecm-rename/paths", json=changed_paths)

    assert updated.status_code == 200
    assert updated.json() == changed_paths
    assert client.get("/api/v1/ecm-rename/paths").json() == changed_paths


def test_preview_extracts_text_and_tracker_values(client, tmp_path) -> None:
    pdf_path = tmp_path / "ECM-TEST.pdf"
    tracker_path = tmp_path / "Tracker.xlsx"
    _write_pdf(pdf_path, PDF_TEXT)
    _write_tracker(tracker_path)

    response = client.post(
        "/api/v1/ecm-rename/preview",
        json={"source_path": str(pdf_path), "tracker_path": str(tracker_path)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sheet_name"] == "ECM Tracker"
    assert [column["name"] for column in body["columns"]] == HEADERS
    assert body["records"][0]["reference"] == "GKN-ECN-123"
    assert body["records"][0]["revision"] == "A@2"
    assert body["records"][0]["subject"] == "Cooling unit update"
    assert body["records"][0]["tracker_values"] == [
        "GKN-ECN-123",
        "A@2",
        "Cooling unit update",
        "Replace component",
        "Sample Engineer",
        "Yes",
        "Update drawing",
    ]


def test_preview_extracts_primary_fields_before_reply_section(client, tmp_path) -> None:
    pdf_path = tmp_path / "ECM-FORM.pdf"
    tracker_path = tmp_path / "Tracker.xlsx"
    form_text = "\n".join(
        [
            "CM-NO.:",
            "DOC-001",
            "COORDINATION MEMO",
            "Revision",
            "00",
            "REPLY TO CM-NO.:",
            "Revision",
            "REFERENCE-002",
            "02",
            "SUBJECT",
            "Example subject",
        ]
    )
    _write_pdf(pdf_path, form_text)
    _write_tracker(tracker_path)

    response = client.post(
        "/api/v1/ecm-rename/preview",
        json={"source_path": str(pdf_path), "tracker_path": str(tracker_path)},
    )

    assert response.status_code == 200
    record = response.json()["records"][0]
    assert record["reference"] == "DOC-001"
    assert record["revision"] == "00"
    assert record["subject"] == "Example subject"


def test_create_folders_copies_pdf_without_updating_tracker(client, tmp_path) -> None:
    pdf_path = tmp_path / "ECM-TEST.pdf"
    tracker_path = tmp_path / "Tracker.xlsx"
    output_path = tmp_path / "output"
    _write_pdf(pdf_path, PDF_TEXT)
    _write_tracker(tracker_path)
    tracker_before = tracker_path.read_bytes()
    original_pdf = pdf_path.read_bytes()

    preview = client.post(
        "/api/v1/ecm-rename/preview",
        json={"source_path": str(pdf_path), "tracker_path": str(tracker_path)},
    ).json()
    record = preview["records"][0]
    record["revision"] = "A@3"
    record["subject"] = "Cooling unit revised"

    response = client.post(
        "/api/v1/ecm-rename/folders",
        json={
            "source_path": preview["source_path"],
            "output_path": str(output_path),
            "records": [
                {
                    "source_path": record["source_path"],
                    "reference": record["reference"],
                    "revision": record["revision"],
                    "subject": record["subject"],
                }
            ],
        },
    )

    assert response.status_code == 200
    result = response.json()
    expected_folder = output_path / "GKN-ECN-123-A@3-Cooling unit revised"
    assert expected_folder.is_dir()
    assert (expected_folder / pdf_path.name).read_bytes() == original_pdf
    assert pdf_path.read_bytes() == original_pdf
    assert result == {"created_folders": [str(expected_folder)]}
    assert tracker_path.read_bytes() == tracker_before


def test_append_tracker_row_without_creating_folders_or_changing_metadata(client, tmp_path) -> None:
    pdf_path = tmp_path / "ECM-TEST.pdf"
    tracker_path = tmp_path / "Tracker.xlsx"
    output_path = tmp_path / "output"
    _write_pdf(pdf_path, PDF_TEXT)
    _write_tracker(tracker_path)
    existing_row = [
        "EXISTING-001",
        "A",
        "Existing subject",
        "Existing title",
        "Existing author",
        "No",
        "No action",
    ]
    workbook = load_workbook(tracker_path)
    workbook.active.append(existing_row)
    workbook.active.add_table(Table(displayName="ECMRecords", ref="A1:G2"))
    untouched_sheet = workbook.create_sheet("Untouched")
    untouched_sheet["A1"] = "Keep this sheet unchanged"
    workbook.properties.creator = "Existing owner"
    workbook.save(tracker_path)
    workbook.close()
    with ZipFile(tracker_path, "a") as archive:
        archive.writestr("customXml/item1.xml", b"<customXml>Preserve this part</customXml>")
    with ZipFile(tracker_path) as archive:
        untouched_parts = {
            name: archive.read(name)
            for name in archive.namelist()
            if name not in {"xl/worksheets/sheet1.xml", "xl/tables/table1.xml"}
        }
    workbook = load_workbook(tracker_path)
    original_modified = workbook.properties.modified
    workbook.close()
    original_pdf = pdf_path.read_bytes()

    preview = client.post(
        "/api/v1/ecm-rename/preview",
        json={"source_path": str(pdf_path), "tracker_path": str(tracker_path)},
    ).json()
    record = preview["records"][0]

    response = client.post(
        "/api/v1/ecm-rename/tracker",
        json={
            "tracker_path": preview["tracker_path"],
            "sheet_name": preview["sheet_name"],
            "header_row": preview["header_row"],
            "records": [{"tracker_values": record["tracker_values"]}],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["rows_written"] == 1
    assert result["tracker_path"] == str(tracker_path)
    assert not output_path.exists()
    with ZipFile(tracker_path) as archive:
        assert {
            name: archive.read(name)
            for name in archive.namelist()
            if name not in {"xl/worksheets/sheet1.xml", "xl/tables/table1.xml"}
        } == untouched_parts

    workbook = load_workbook(tracker_path, data_only=True)
    try:
        rows = list(workbook.active.values)
        assert rows[1] == tuple(existing_row)
        assert rows[2] == tuple(record["tracker_values"])
        assert workbook.properties.creator == "Existing owner"
        assert workbook.properties.modified == original_modified
        assert workbook["ECM Tracker"].tables["ECMRecords"].ref == "A1:G3"
    finally:
        workbook.close()
    assert not list(tmp_path.glob("Tracker_backup_*.xlsx"))


def test_preview_rejects_scanned_pdf_without_ocr(client, tmp_path) -> None:
    pdf_path = tmp_path / "scanned.pdf"
    tracker_path = tmp_path / "Tracker.xlsx"
    _write_pdf(pdf_path, "")
    _write_tracker(tracker_path)

    response = client.post(
        "/api/v1/ecm-rename/preview",
        json={"source_path": str(pdf_path), "tracker_path": str(tracker_path)},
    )

    assert response.status_code == 400
    assert "OCR n'est pas activé" in response.json()["message"]


def test_preview_scans_multiple_pdfs_in_selected_folder(client, tmp_path) -> None:
    source_folder = tmp_path / "to process"
    source_folder.mkdir()
    tracker_path = tmp_path / "Tracker.xlsx"
    _write_pdf(source_folder / "ECN-B.pdf", PDF_TEXT.replace("GKN-ECN-123", "GKN-ECN-124"))
    _write_pdf(source_folder / "ECN-A.pdf", PDF_TEXT)
    (source_folder / "notes.txt").write_text("not a PDF", encoding="utf-8")
    _write_tracker(tracker_path)

    response = client.post(
        "/api/v1/ecm-rename/preview",
        json={"source_path": str(source_folder), "tracker_path": str(tracker_path)},
    )

    assert response.status_code == 200
    body = response.json()
    assert [record["file_name"] for record in body["records"]] == ["ECN-A.pdf", "ECN-B.pdf"]
    assert [record["reference"] for record in body["records"]] == ["GKN-ECN-123", "GKN-ECN-124"]
    assert all(record["tracker_values"][-1] == "Update drawing" for record in body["records"])


@pytest.mark.parametrize(
    ("kind", "selected_path"),
    [
        ("source_file", r"C:\ECM\ECN.pdf"),
        ("source_directory", r"C:\ECM\à traiter"),
        ("tracker_file", r"C:\ECM\tracker.xlsx"),
        ("output_directory", r"C:\ECM\sortie"),
        ("output_directory", ""),
    ],
)
def test_browse_path_uses_native_picker_and_returns_selection(
    client, monkeypatch, kind: str, selected_path: str
) -> None:
    from app.api import ecm_rename as ecm_rename_route

    picker_calls = []

    def select_path(request_kind: str, current_path: str | None, language: str) -> str:
        picker_calls.append((request_kind, current_path, language))
        return selected_path

    monkeypatch.setattr(ecm_rename_route, "choose_path", select_path)

    response = client.post(
        "/api/v1/ecm-rename/browse",
        json={"kind": kind, "current_path": r"C:\ECM", "language": "fr"},
    )

    assert response.status_code == 200
    assert response.json() == {"path": selected_path or None}
    assert picker_calls == [(kind, r"C:\ECM", "fr")]


@pytest.mark.parametrize(
    ("kind", "selected_path"),
    [
        ("source_file", r"C:\ECM\ECN.pdf"),
        ("source_directory", r"C:\ECM\à traiter"),
        ("tracker_file", r"C:\ECM\tracker.xlsx"),
        ("output_directory", ""),
    ],
)
def test_windows_picker_uses_powershell_without_exposing_other_environment(
    monkeypatch, kind: BrowseKind, selected_path: str
) -> None:
    import subprocess

    from app.services import path_picker

    captured = {}
    powershell_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

    monkeypatch.setattr(
        path_picker.shutil,
        "which",
        lambda name: powershell_path if name == "powershell.exe" else None,
    )

    def run_picker(command, **options):
        captured["command"] = command
        captured["options"] = options
        return subprocess.CompletedProcess(command, 0, stdout=f"{selected_path}\r\n", stderr="")

    monkeypatch.setattr(path_picker.subprocess, "run", run_picker)

    result = path_picker._pick_with_windows(kind, "Select", "en", r"C:\ECM")

    assert result == selected_path or result is None
    assert "-STA" in captured["command"]
    assert captured["options"]["env"]["ECM_RENAME_PICKER_KIND"] == kind
    assert captured["options"]["env"]["ECM_RENAME_PICKER_INITIAL_DIRECTORY"] == r"C:\ECM"
    assert "MISTRAL_API_KEY" not in captured["options"]["env"]
