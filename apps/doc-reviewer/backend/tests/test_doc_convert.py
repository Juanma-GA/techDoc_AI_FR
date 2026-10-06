"""`doc_convert` logging — M-08 hardening.

`_convert_libreoffice_format` calls `log.info(...)` / `log.warning(...)` with
structlog-style keyword arguments (`target_format=...`, `error=...`). Before
this fix, `log` was a stdlib `logging.Logger`, which raises `TypeError` on an
unexpected keyword argument — the same class of bug fixed in `mistral_settings`
(H-03). Here it was worse: the `log.warning(...)` call in the `except` block
itself would raise, propagating out of `_convert_libreoffice_format` instead
of returning `None`, breaking every `.doc`/`.docx` conversion path whenever
LibreOffice failed (or even succeeded, via the `log.info` call)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.core import doc_convert


def test_convert_libreoffice_format_success_path_does_not_crash_on_logging(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(doc_convert, "_find_soffice", lambda: "soffice")

    def fake_run(*_args, **_kwargs):
        (tmp_path / "input.docx").write_bytes(b"PK\x03\x04")
        return subprocess.CompletedProcess(args=[], returncode=0)

    monkeypatch.setattr(doc_convert.subprocess, "run", fake_run)

    src = tmp_path / "input.doc"
    src.write_bytes(b"synthetic")

    out = doc_convert._convert_libreoffice_format(src, tmp_path, "docx")

    assert out == tmp_path / "input.docx"


def test_convert_libreoffice_format_failure_path_does_not_crash_on_logging(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(doc_convert, "_find_soffice", lambda: "soffice")

    def fake_run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=["soffice"])

    monkeypatch.setattr(doc_convert.subprocess, "run", fake_run)

    src = tmp_path / "input.doc"
    src.write_bytes(b"synthetic")

    out = doc_convert._convert_libreoffice_format(src, tmp_path, "docx")

    assert out is None
