"""Recoverable parser failures remain observable in structured logs."""

from types import SimpleNamespace

import pytest
import structlog
from structlog.testing import capture_logs

from app.parsers import docx_parser, pdf_parser


@pytest.mark.parametrize(("operation", "event"), [
    ("images", "pdf_image_info_failed"),
    ("tables", "pdf_table_detection_failed"),
    ("table_rows", "pdf_table_extraction_failed"),
])
def test_pdf_fallback_logs_page_and_exception(monkeypatch, operation, event) -> None:
    def fail():
        raise RuntimeError("Synthetic PDF parser failure")

    page = SimpleNamespace(number=2)
    if operation == "images":
        page.get_image_info = fail
    elif operation == "tables":
        page.find_tables = fail
    else:
        page.find_tables = lambda: SimpleNamespace(tables=[SimpleNamespace(extract=fail)])

    with capture_logs() as logs:
        monkeypatch.setattr(pdf_parser, "log", structlog.get_logger())
        if operation == "images":
            assert pdf_parser._image_infos(page) == []
        else:
            assert pdf_parser._table_blocks(page, 3, None) == ([], [])
    assert logs[0]["event"] == event
    assert logs[0]["page"] == 3
    assert logs[0]["error_type"] == "RuntimeError"
    assert logs[0]["exc_info"] is True


def test_missing_docx_numbering_is_logged(monkeypatch) -> None:
    class Part:
        @property
        def numbering_part(self):
            raise NotImplementedError("Synthetic missing numbering")

    with capture_logs() as logs:
        monkeypatch.setattr(docx_parser, "log", structlog.get_logger())
        assert docx_parser._numbering_map(SimpleNamespace(part=Part())) == {}
    assert logs[0]["event"] == "docx_numbering_unavailable"
    assert logs[0]["error_type"] == "NotImplementedError"
    assert logs[0]["exc_info"] is True


def test_orphaned_pdf_page_failure_does_not_hide_the_original_exception(monkeypatch) -> None:
    def fail():
        raise ValueError("Synthetic orphaned page")

    page = SimpleNamespace(number=None, get_image_info=fail)
    with capture_logs() as logs:
        monkeypatch.setattr(pdf_parser, "log", structlog.get_logger())
        assert pdf_parser._image_infos(page) == []
    assert logs[0]["page"] is None
    assert logs[0]["error_type"] == "ValueError"
