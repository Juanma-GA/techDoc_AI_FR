from __future__ import annotations

import fitz
import pytest
from openpyxl import Workbook, load_workbook

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


def test_process_creates_folder_copies_pdf_and_appends_tracker_row(client, tmp_path) -> None:
    pdf_path = tmp_path / "ECM-TEST.pdf"
    tracker_path = tmp_path / "Tracker.xlsx"
    output_path = tmp_path / "output"
    _write_pdf(pdf_path, PDF_TEXT)
    _write_tracker(tracker_path)

    preview = client.post(
        "/api/v1/ecm-rename/preview",
        json={"source_path": str(pdf_path), "tracker_path": str(tracker_path)},
    ).json()
    record = preview["records"][0]
    record["revision"] = "A@3"
    record["subject"] = "Cooling unit revised"
    record["tracker_values"][1] = record["revision"]
    record["tracker_values"][2] = record["subject"]

    response = client.post(
        "/api/v1/ecm-rename/process",
        json={
            "source_path": preview["source_path"],
            "tracker_path": preview["tracker_path"],
            "output_path": str(output_path),
            "sheet_name": preview["sheet_name"],
            "header_row": preview["header_row"],
            "records": [record],
        },
    )

    assert response.status_code == 200
    result = response.json()
    expected_folder = output_path / "GKN-ECN-123-A@3-Cooling unit revised"
    assert expected_folder.is_dir()
    assert (expected_folder / pdf_path.name).read_bytes() == pdf_path.read_bytes()
    assert result["rows_written"] == 1
    assert result["backup_path"]

    workbook = load_workbook(tracker_path, data_only=True)
    try:
        assert list(workbook.active.values)[1] == tuple(record["tracker_values"])
    finally:
        workbook.close()
    assert list(tmp_path.glob("Tracker_backup_*.xlsx"))


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