"""Pytest fixtures — force in-memory SQLite for isolation."""

from __future__ import annotations

import os
from copy import copy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from openpyxl import load_workbook
from openpyxl.utils.cell import get_column_letter, range_boundaries

os.environ["DATABASE_URL"] = "sqlite:///:memory:"


class _ExcelRange:
    def __init__(
        self,
        sheet: _ExcelSheet,
        first_row: int,
        first_column: int,
        last_row: int,
        last_column: int,
    ) -> None:
        self.sheet = sheet
        self.first_row = first_row
        self.first_column = first_column
        self.last_row = last_row
        self.last_column = last_column
        self.ndim: int | None = None

    def options(self, *, ndim: int | None = None, **_: Any) -> _ExcelRange:
        self.ndim = ndim
        return self

    def _values(self) -> list[list[Any]]:
        return [
            [
                self.sheet.worksheet.cell(row, column).value
                for column in range(self.first_column, self.last_column + 1)
            ]
            for row in range(self.first_row, self.last_row + 1)
        ]

    @property
    def value(self) -> Any:
        values = self._values()
        if self.ndim == 2:
            return values
        if self.ndim == 1:
            if self.first_row == self.last_row:
                return values[0]
            if self.first_column == self.last_column:
                return [row[0] for row in values]
        if self.first_row == self.last_row and self.first_column == self.last_column:
            return values[0][0]
        return values

    @value.setter
    def value(self, value: Any) -> None:
        if self.first_row == self.last_row and self.first_column == self.last_column:
            self.sheet.worksheet.cell(self.first_row, self.first_column).value = value
            return
        rows = value if value and isinstance(value[0], list) else [value]
        for row_offset, row_values in enumerate(rows):
            for column_offset, cell_value in enumerate(row_values):
                self.sheet.worksheet.cell(
                    self.first_row + row_offset,
                    self.first_column + column_offset,
                ).value = cell_value

    @property
    def formula(self) -> Any:
        return self.value

    def clear_contents(self) -> None:
        self.value = None

    def copy(self, destination: _ExcelRange) -> None:
        for row_offset in range(self.last_row - self.first_row + 1):
            for column_offset in range(self.last_column - self.first_column + 1):
                source = self.sheet.worksheet.cell(
                    self.first_row + row_offset,
                    self.first_column + column_offset,
                )
                target = destination.sheet.worksheet.cell(
                    destination.first_row + row_offset,
                    destination.first_column + column_offset,
                )
                target.value = source.value
                if source.has_style:
                    target._style = copy(source._style)
                if source.hyperlink:
                    target._hyperlink = copy(source.hyperlink)


class _ExcelSheet:
    def __init__(self, book: _ExcelBook, worksheet: Any) -> None:
        self.book = book
        self.worksheet = worksheet
        self.name = worksheet.title

    @property
    def used_range(self) -> SimpleNamespace:
        last_cell = SimpleNamespace(
            row=max(self.worksheet.max_row, 1),
            column=max(self.worksheet.max_column, 1),
        )
        return SimpleNamespace(last_cell=last_cell)

    @property
    def api(self) -> SimpleNamespace:
        tables = [_ExcelTable(self, table) for table in self.worksheet.tables.values()]
        return SimpleNamespace(ListObjects=tables)

    def range(self, start: tuple[int, int], end: tuple[int, int] | None = None) -> _ExcelRange:
        last = end or start
        return _ExcelRange(self, start[0], start[1], last[0], last[1])


class _ExcelSheets:
    def __init__(self, book: _ExcelBook) -> None:
        self.book = book

    @property
    def active(self) -> _ExcelSheet:
        return _ExcelSheet(self.book, self.book.workbook.active)

    def __iter__(self):
        return (_ExcelSheet(self.book, worksheet) for worksheet in self.book.workbook.worksheets)

    def __getitem__(self, name: str) -> _ExcelSheet:
        return _ExcelSheet(self.book, self.book.workbook[name])


class _ExcelTable:
    def __init__(self, sheet: _ExcelSheet, table: Any) -> None:
        self.sheet = sheet
        self.table = table

    def _bounds(self) -> tuple[int, int, int, int]:
        return range_boundaries(self.table.ref)

    @property
    def Range(self) -> SimpleNamespace:  # noqa: N802
        min_column, min_row, max_column, max_row = self._bounds()
        return SimpleNamespace(
            Row=min_row,
            Column=min_column,
            Columns=SimpleNamespace(Count=max_column - min_column + 1),
            Rows=SimpleNamespace(Count=max_row - min_row + 1),
        )

    @property
    def DataBodyRange(self) -> _ExcelRange | None:  # noqa: N802
        min_column, min_row, max_column, max_row = self._bounds()
        if max_row <= min_row:
            return None
        body = _ExcelRange(self.sheet, min_row + 1, min_column, max_row, max_column)
        body.Row = min_row + 1
        body.Rows = SimpleNamespace(Count=max_row - min_row)
        return body

    @property
    def ListRows(self) -> SimpleNamespace:  # noqa: N802
        return SimpleNamespace(Add=self._add_row)

    def _add_row(self) -> SimpleNamespace:
        min_column, min_row, max_column, max_row = self._bounds()
        new_row = max_row + 1
        self.sheet.worksheet.insert_rows(new_row)
        self.table.ref = (
            f"{get_column_letter(min_column)}{min_row}:"
            f"{get_column_letter(max_column)}{new_row}"
        )
        return SimpleNamespace(Range=SimpleNamespace(Row=new_row))


class _ExcelBook:
    def __init__(self, workbook: Any, app: _ExcelApp, path: str, *, read_only: bool) -> None:
        self.workbook = workbook
        self.app = app
        self.path = path
        self.api = SimpleNamespace(ReadOnly=read_only)
        self.sheets = _ExcelSheets(self)

    def save(self) -> None:
        self.workbook.save(self.path)

    def close(self) -> None:
        self.workbook.close()


class _ExcelBooks:
    def __init__(self, app: _ExcelApp) -> None:
        self.app = app

    def open(self, path: str, *, read_only: bool = False, **_: Any) -> _ExcelBook:
        workbook = load_workbook(
            path,
            keep_vba=Path(path).suffix.lower() == ".xlsm",
        )
        return _ExcelBook(workbook, self.app, path, read_only=read_only)


class _ExcelApp:
    def __init__(self, **_: Any) -> None:
        self.api = SimpleNamespace()
        self.books = _ExcelBooks(self)

    def quit(self) -> None:
        pass


@pytest.fixture(autouse=True)
def mock_excel(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import ecm_automation_tracker_3

    monkeypatch.setattr(ecm_automation_tracker_3.xw, "App", _ExcelApp)


@pytest.fixture
def app():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db.session import Base, get_db
    from app.main import create_app

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    test_session = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    def get_test_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    application = create_app()
    application.dependency_overrides[get_db] = get_test_db
    yield application
    test_engine.dispose()


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    return TestClient(app)
