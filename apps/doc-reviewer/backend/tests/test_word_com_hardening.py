"""Word COM : aucune macro ne s'execute a l'ouverture d'un document non fiable."""

from __future__ import annotations

import pathlib
import sys
import types

import pytest


# ---------------------------------------------------------------------------
# Word COM : jamais de macro a l'ouverture d'un document non fiable
# ---------------------------------------------------------------------------


class _FakeWordDoc:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def ExportAsFixedFormat(self, OutputFileName: str, ExportFormat: int) -> None:  # noqa: N802,N803
        self._events.append("export")
        pathlib.Path(OutputFileName).write_bytes(b"%PDF-1.4 fake")

    def Close(self, _save: bool) -> None:  # noqa: N802
        self._events.append("close")


class _FakeDocuments:
    def __init__(self, word: "_FakeWord") -> None:
        self._word = word

    def Open(self, **kwargs: object) -> _FakeWordDoc:  # noqa: N802
        self._word.events.append(f"open(security={self._word.AutomationSecurity})")
        self._word.open_kwargs = kwargs
        return _FakeWordDoc(self._word.events)


class _FakeWord:
    def __init__(self, sticky: bool = True) -> None:
        self.events: list[str] = []
        self.open_kwargs: dict[str, object] = {}
        self._security = 1  # msoAutomationSecurityLow : defaut COM (macros actives)
        self._sticky = sticky
        self.Visible = True
        self.DisplayAlerts = -1
        self.Documents = _FakeDocuments(self)

    @property
    def AutomationSecurity(self) -> int:  # noqa: N802
        return self._security

    @AutomationSecurity.setter
    def AutomationSecurity(self, value: int) -> None:  # noqa: N802
        self.events.append(f"set_security({value})")
        if self._sticky:
            self._security = value

    def Quit(self) -> None:  # noqa: N802
        self.events.append("quit")


def _install_fake_com(monkeypatch: pytest.MonkeyPatch, word: _FakeWord) -> None:
    pythoncom = types.ModuleType("pythoncom")
    pythoncom.CoInitialize = lambda: None  # type: ignore[attr-defined]
    pythoncom.CoUninitialize = lambda: None  # type: ignore[attr-defined]
    client = types.ModuleType("win32com.client")
    client.DispatchEx = lambda _progid: word  # type: ignore[attr-defined]
    package = types.ModuleType("win32com")
    package.client = client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    monkeypatch.setitem(sys.modules, "win32com", package)
    monkeypatch.setitem(sys.modules, "win32com.client", client)


def test_word_com_disables_macros_before_opening(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    from app.core import doc_convert

    word = _FakeWord()
    _install_fake_com(monkeypatch, word)
    src = tmp_path / "input.docx"
    src.write_bytes(b"PK fake")
    produced, error = doc_convert._word_export_pdf(src, tmp_path / "out.pdf")

    assert error is None and produced is not None
    assert word.events[0] == "set_security(3)"
    assert "open(security=3)" in word.events
    assert word.open_kwargs["ReadOnly"] is True
    assert word.open_kwargs["OpenAndRepair"] is False
    assert word.open_kwargs["PasswordDocument"]
    assert word.Visible is False and word.DisplayAlerts == 0


def test_word_com_refuses_to_open_when_macros_cannot_be_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    from app.core import doc_convert

    word = _FakeWord(sticky=False)
    _install_fake_com(monkeypatch, word)
    src = tmp_path / "input.doc"
    src.write_bytes(b"fake")
    produced, error = doc_convert._word_export_pdf(src, tmp_path / "out.pdf")

    assert produced is None and error
    assert not any(event.startswith("open(") for event in word.events)
    assert "quit" in word.events
