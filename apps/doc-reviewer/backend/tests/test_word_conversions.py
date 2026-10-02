"""Conversions par Microsoft Word : etiquette Purview, ordre des moteurs, garde-fou.

Word est simule (aucun Office requis). Les conversions reelles sont couvertes
par `test_word_real.py` (opt-in, poste Windows avec Word)."""

from __future__ import annotations

import io
import pathlib
import sys
import threading
import types
import zipfile

import pytest

from app.config import settings
from app.core import doc_convert
from app.core.errors import AppError

LABEL_C2 = "f44e79de-7414-4831-b055-2e5a46a0d301"
DOC = bytes.fromhex("D0CF11E0A1B11AE1") + b"legacy word 97 body"
PDF = b"%PDF-1.7 source"


def _docx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


DOCX = _docx()


class _LabelInfo:
    LabelId = ""
    AssignmentMethod = None
    Justification = ""


class _Sensitivity:
    def __init__(self, events: list[str], existing: str) -> None:
        self._events = events
        self._existing = existing

    def GetLabel(self) -> _LabelInfo:  # noqa: N802
        info = _LabelInfo()
        info.LabelId = self._existing
        return info

    def CreateLabelInfo(self) -> _LabelInfo:  # noqa: N802
        return _LabelInfo()

    def SetLabel(self, info: _LabelInfo, _context: object) -> None:  # noqa: N802
        self._events.append(f"set_label({info.LabelId},{info.AssignmentMethod})")
        self._existing = info.LabelId


class _Doc:
    def __init__(self, word: _Word) -> None:
        self._word = word
        self.SensitivityLabel = _Sensitivity(word.events, word.existing_label)

    def ExportAsFixedFormat(self, OutputFileName: str, ExportFormat: int) -> None:  # noqa: N802,N803
        self._word.events.append(f"export({ExportFormat})")
        if self._word.block is not None:
            self._word.block.wait()
            raise RuntimeError("The RPC server is unavailable.")
        pathlib.Path(OutputFileName).write_bytes(b"%PDF-1.7 fake")

    def SaveAs2(self, FileName: str, FileFormat: int) -> None:  # noqa: N802,N803
        self._word.events.append(f"save({FileFormat})")
        if FileFormat == 16 and self._word.mandatory_label and not self.SensitivityLabel._existing:
            raise RuntimeError(
                "(-2147352567, 'Exception occurred.', (0, 'Microsoft Word', 'Command failed'))"
            )
        pathlib.Path(FileName).write_bytes(b"PK fake")

    def Close(self, _save: bool) -> None:  # noqa: N802
        self._word.events.append("close")


class _Documents:
    def __init__(self, word: _Word) -> None:
        self._word = word

    def Open(self, **kwargs: object) -> _Doc:  # noqa: N802
        self._word.events.append(f"open({pathlib.Path(str(kwargs['FileName'])).suffix})")
        return _Doc(self._word)


class _Word:
    Version = "16.0"

    def __init__(self, *, mandatory_label: bool = True, existing_label: str = "") -> None:
        self.events: list[str] = []
        self.mandatory_label = mandatory_label
        self.existing_label = existing_label
        self.block: threading.Event | None = None
        self.AutomationSecurity = 1
        self.Visible = True
        self.DisplayAlerts = -1
        self.Caption = ""
        self.Documents = _Documents(self)

    def Quit(self) -> None:  # noqa: N802
        self.events.append("quit")


@pytest.fixture
def fake_word(monkeypatch: pytest.MonkeyPatch):
    def install(word: _Word) -> _Word:
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
        monkeypatch.setattr(doc_convert, "_word_pid", lambda _caption: None)
        monkeypatch.setattr(
            doc_convert, "_disable_pdf_reflow_prompt", lambda _v: word.events.append("pdf_prompt_off")
        )
        monkeypatch.setattr(doc_convert, "_find_soffice", lambda: None)
        monkeypatch.setattr(settings, "office_converter", "auto")
        monkeypatch.setattr(settings, "word_sensitivity_label_id", "")
        return word

    return install


def test_doc_to_docx_sets_the_configured_label_before_saving(fake_word, monkeypatch) -> None:
    word = fake_word(_Word())
    monkeypatch.setattr(settings, "word_sensitivity_label_id", LABEL_C2)

    data, engine = doc_convert.office_to_docx_bytes(DOC, ".doc")

    assert data == b"PK fake" and engine == "word"
    assert word.events.index(f"set_label({LABEL_C2},1)") < word.events.index("save(16)")
    assert word.Caption.startswith("doc-reviewer-")


def test_an_existing_label_is_kept(fake_word, monkeypatch) -> None:
    word = fake_word(_Word(existing_label="3f595d1a-a546-4e1d-a62e-643892992159"))
    monkeypatch.setattr(settings, "word_sensitivity_label_id", LABEL_C2)

    doc_convert.office_to_docx_bytes(DOC, ".doc")

    assert not any(e.startswith("set_label") for e in word.events)
    assert "save(16)" in word.events


def test_missing_label_setting_explains_what_to_configure(fake_word) -> None:
    word = fake_word(_Word(mandatory_label=True))

    with pytest.raises(AppError) as err:
        doc_convert.office_to_docx_bytes(DOC, ".doc")

    assert err.value.code == "DOC_CONVERT_UNAVAILABLE"
    assert "WORD_SENSITIVITY_LABEL_ID" in err.value.message
    assert "quit" in word.events


def test_no_label_needed_when_the_tenant_does_not_mandate_one(fake_word) -> None:
    word = fake_word(_Word(mandatory_label=False))

    data, _ = doc_convert.office_to_docx_bytes(DOC, ".doc")

    assert data == b"PK fake"
    assert not any(e.startswith("set_label") for e in word.events)


def test_every_conversion_uses_word(fake_word, monkeypatch) -> None:
    word = fake_word(_Word())
    monkeypatch.setattr(settings, "word_sensitivity_label_id", LABEL_C2)

    pdf, engine = doc_convert.doc_to_pdf_bytes(DOC, ".doc")
    assert pdf.startswith(b"%PDF") and engine == "word"
    assert doc_convert.docx_to_doc_bytes(DOCX) == b"PK fake"
    assert doc_convert.pdf_to_docx_bytes(PDF) == b"PK fake"
    assert doc_convert.pdf_to_doc_bytes(PDF) == b"PK fake"

    assert "export(17)" in word.events
    assert "save(0)" in word.events
    assert word.events.count("pdf_prompt_off") == 2  # only for the two PDF sources


def test_docx_to_doc_does_not_touch_labels(fake_word, monkeypatch) -> None:
    word = fake_word(_Word())
    monkeypatch.setattr(settings, "word_sensitivity_label_id", LABEL_C2)

    doc_convert.docx_to_doc_bytes(DOCX)

    assert not any(e.startswith("set_label") for e in word.events)


def test_libreoffice_is_the_fallback_in_auto_mode(fake_word, monkeypatch, tmp_path) -> None:
    fake_word(_Word())  # mandatory label, none configured -> Word refuses the .docx
    calls: list[str] = []

    def fake_lo(src: pathlib.Path, outdir: pathlib.Path, target: str) -> pathlib.Path:
        calls.append(target)
        out = outdir / f"{src.stem}.{target}"
        out.write_bytes(b"PK from libreoffice")
        return out

    monkeypatch.setattr(doc_convert, "_convert_libreoffice_format", fake_lo)

    data, engine = doc_convert.office_to_docx_bytes(DOC, ".doc")

    assert (data, engine) == (b"PK from libreoffice", "libreoffice")
    assert calls == ["docx"]


def test_word_only_mode_never_calls_libreoffice(fake_word, monkeypatch) -> None:
    fake_word(_Word())
    monkeypatch.setattr(settings, "office_converter", "word")
    monkeypatch.setattr(
        doc_convert, "_convert_libreoffice_format", lambda *_a: pytest.fail("LibreOffice called")
    )

    with pytest.raises(AppError):
        doc_convert.office_to_docx_bytes(DOC, ".doc")


def test_libreoffice_only_mode_never_starts_word(monkeypatch) -> None:
    monkeypatch.setattr(settings, "office_converter", "libreoffice")
    monkeypatch.setattr(doc_convert, "_word_convert", lambda *_a: pytest.fail("Word started"))
    monkeypatch.setattr(doc_convert, "_convert_libreoffice_format", lambda *_a: None)

    with pytest.raises(AppError) as err:
        doc_convert.doc_to_pdf_bytes(DOCX, ".docx")
    assert err.value.status_code == 400


def test_pdf_conversion_failures_are_409(fake_word, monkeypatch) -> None:
    fake_word(_Word())
    monkeypatch.setattr(settings, "office_converter", "word")

    with pytest.raises(AppError) as err:
        doc_convert.pdf_to_docx_bytes(PDF)
    assert err.value.status_code == 409


def test_watchdog_stops_only_the_stuck_word_instance(fake_word, monkeypatch) -> None:
    word = fake_word(_Word())
    word.block = threading.Event()
    killed: list[int] = []
    monkeypatch.setattr(settings, "word_convert_timeout_seconds", 1)
    monkeypatch.setattr(doc_convert, "_word_pid", lambda _caption: 4242)

    def fake_kill(pid: int) -> None:
        killed.append(pid)
        word.block.set()  # what killing WINWORD does to the pending COM call

    monkeypatch.setattr(doc_convert, "_kill_pid", fake_kill)

    with pytest.raises(AppError):
        doc_convert.doc_to_pdf_bytes(DOC, ".doc")

    assert killed == [4242]


def test_watchdog_does_not_fire_on_a_normal_conversion(fake_word, monkeypatch) -> None:
    fake_word(_Word())
    killed: list[int] = []
    monkeypatch.setattr(settings, "word_convert_timeout_seconds", 1)
    monkeypatch.setattr(doc_convert, "_word_pid", lambda _caption: 4242)
    monkeypatch.setattr(doc_convert, "_kill_pid", killed.append)

    doc_convert.doc_to_pdf_bytes(DOC, ".doc")
    threading.Event().wait(1.5)

    assert killed == []


def test_can_convert_formats_follows_the_configured_engines(monkeypatch) -> None:
    monkeypatch.setattr(doc_convert, "word_available", lambda: True)
    monkeypatch.setattr(doc_convert, "_find_soffice", lambda: None)
    monkeypatch.setattr(settings, "office_converter", "auto")
    assert doc_convert.can_convert_formats() is True
    monkeypatch.setattr(settings, "office_converter", "libreoffice")
    assert doc_convert.can_convert_formats() is False


def test_a_transient_word_failure_is_retried_once_with_a_new_instance(fake_word, monkeypatch) -> None:
    word = fake_word(_Word())
    original = _Doc.ExportAsFixedFormat
    failures = iter([True])

    def flaky(self, OutputFileName: str, ExportFormat: int) -> None:  # noqa: N803
        if next(failures, False):
            raise RuntimeError("(-2147418111, 'Call was rejected by callee.', None, None)")
        original(self, OutputFileName, ExportFormat)

    monkeypatch.setattr(_Doc, "ExportAsFixedFormat", flaky)

    pdf, _ = doc_convert.doc_to_pdf_bytes(DOC, ".doc")

    assert pdf.startswith(b"%PDF")
    assert word.events.count("quit") == 2


def test_a_label_refusal_is_not_retried(fake_word) -> None:
    word = fake_word(_Word(mandatory_label=True))

    with pytest.raises(AppError):
        doc_convert.office_to_docx_bytes(DOC, ".doc")

    assert word.events.count("save(16)") == 1


def test_a_watchdog_stop_is_not_retried(fake_word, monkeypatch) -> None:
    word = fake_word(_Word())
    word.block = threading.Event()
    killed: list[int] = []
    monkeypatch.setattr(settings, "word_convert_timeout_seconds", 1)
    monkeypatch.setattr(doc_convert, "_word_pid", lambda _caption: 4242)

    def fake_kill(pid: int) -> None:
        killed.append(pid)
        word.block.set()

    monkeypatch.setattr(doc_convert, "_kill_pid", fake_kill)

    with pytest.raises(AppError) as err:
        doc_convert.doc_to_pdf_bytes(DOC, ".doc")

    assert killed == [4242]
    assert word.events.count("export(17)") == 1
    assert "garde-fou" in str(err.value.detail)


@pytest.mark.parametrize(
    ("data", "suffix"),
    [
        (b"{\\rtf1\\ansi exploit}", ".doc"),  # RTF renamed .doc
        (b"<html><body>x</body></html>", ".doc"),  # HTML renamed .doc
        (b"MIME-Version: 1.0", ".doc"),  # MHT renamed .doc
        (b"plain text", ".doc"),
        (b"PK\x03\x04 not a zip", ".docx"),
        (DOC, ".docx"),
        (b"<html>", ".pdf"),
    ],
)
def test_content_that_is_not_the_announced_format_never_reaches_word(
    fake_word, data: bytes, suffix: str
) -> None:
    word = fake_word(_Word())

    with pytest.raises(AppError) as err:
        if suffix == ".pdf":
            doc_convert.pdf_to_docx_bytes(data)
        elif suffix == ".docx":
            doc_convert.doc_to_pdf_bytes(data, suffix)
        else:
            doc_convert.office_to_docx_bytes(data, suffix)

    assert err.value.code == "DOC_INVALID" and err.value.status_code == 400
    assert word.events == []  # Word was never started


def _crash_on_close(monkeypatch: pytest.MonkeyPatch) -> None:
    def close(self, _save: bool) -> None:
        self._word.events.append("close")
        raise RuntimeError("(-2147417848, 'The object invoked has disconnected from its clients.')")

    monkeypatch.setattr(_Doc, "Close", close)


def test_word_crashing_on_close_after_writing_keeps_the_result(fake_word, monkeypatch) -> None:
    word = fake_word(_Word())
    _crash_on_close(monkeypatch)

    pdf, engine = doc_convert.doc_to_pdf_bytes(DOC, ".doc")

    assert pdf.startswith(b"%PDF") and engine == "word"
    assert word.events.count("export(17)") == 1  # no retry: the file was complete


def test_word_crashing_before_the_file_is_written_is_a_failure(fake_word, monkeypatch) -> None:
    fake_word(_Word(mandatory_label=True))  # SaveAs2 .docx refused, then Close crashes too
    _crash_on_close(monkeypatch)

    with pytest.raises(AppError):
        doc_convert.office_to_docx_bytes(DOC, ".doc")


@pytest.mark.parametrize(("suffix", "imports_as_writer"), [(".pdf", True), (".doc", False), (".docx", False)])
def test_libreoffice_opens_a_pdf_in_writer(suffix, imports_as_writer) -> None:
    """LibreOffice opens a PDF in Draw, which cannot export .docx/.doc."""
    cmd = doc_convert._libreoffice_command(
        "soffice", pathlib.Path(f"input{suffix}"), pathlib.Path("out"), "docx"
    )
    assert ("--infilter=writer_pdf_import" in cmd) is imports_as_writer
    assert cmd[-5:] == ["--convert-to", "docx", "--outdir", "out", f"input{suffix}"]


def test_soffice_path_from_the_settings_file(tmp_path, monkeypatch) -> None:
    """DR_SOFFICE_PATH written in backend/.env (not only the environment) is used."""
    exe = tmp_path / "soffice.exe"
    exe.write_bytes(b"")
    monkeypatch.delenv("DR_SOFFICE_PATH", raising=False)
    monkeypatch.setattr(settings, "dr_soffice_path", str(tmp_path))
    assert doc_convert._find_soffice() == str(exe)
