"""Unit tests for CATIA Composer Converter integration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import composer_converter


def test_detect_executable_uses_valid_configured_path(tmp_path: Path) -> None:
    executable = tmp_path / "ComposerConverter.exe"
    executable.write_text("synthetic executable", encoding="utf-8")

    assert composer_converter.detect_executable(str(executable)) == executable.resolve()


def test_detect_executable_rejects_missing_configured_path(tmp_path: Path) -> None:
    assert composer_converter.detect_executable(str(tmp_path / "missing.exe")) is None


def test_build_command_uses_official_converter_contract(tmp_path: Path) -> None:
    source = tmp_path / "part.CATPart"
    status = composer_converter.ComposerConverterStatus(
        available=True,
        executable=r"C:\CATIAComposer\ComposerConverter.exe",
        settings_file=r"C:\CATIAComposer\conversion.xml",
        version="7.11",
        message="ready",
    )

    assert composer_converter.build_command(status, source) == [
        status.executable,
        str(source),
        status.settings_file,
    ]


def test_build_command_rejects_unavailable_converter() -> None:
    status = composer_converter.ComposerConverterStatus(False, "", "", "", "profile missing")

    with pytest.raises(ValueError, match="profile missing"):
        composer_converter.build_command(status, Path("part.CATPart"))


def test_find_generated_file_accepts_composer_native_outputs(tmp_path: Path) -> None:
    source = tmp_path / "part.CATPart"
    target = tmp_path / "output" / "part.smgxml"
    generated = source.with_suffix(".smgXml")
    generated.write_text("synthetic Composer output", encoding="utf-8")

    assert composer_converter.find_generated_file(source, target) == generated


def test_find_generated_file_rejects_unchanged_previous_output(tmp_path: Path) -> None:
    source = tmp_path / "part.CATPart"
    target = tmp_path / "output" / "part.smgxml"
    generated = source.with_suffix(".smgXml")
    generated.write_text("old Composer output", encoding="utf-8")
    previous = composer_converter.snapshot_outputs(source, target)

    assert composer_converter.find_generated_file(source, target, previous) is None

    generated.write_text("new Composer output with changed size", encoding="utf-8")
    assert composer_converter.find_generated_file(source, target, previous) == generated


def test_execute_plan_runs_converter_and_moves_output(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "part.CATPart"
    source.write_text("synthetic source", encoding="utf-8")
    item = SimpleNamespace(source_path="part.CATPart", target_path="converted/part.smgxml")
    status = composer_converter.ComposerConverterStatus(
        True,
        r"C:\CATIAComposer\ComposerConverter.exe",
        r"C:\CATIAComposer\conversion.xml",
        "7.11",
        "ready",
    )
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured.update(command=command, **kwargs)
        source.with_suffix(".smgXml").write_text("synthetic output", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="converted", stderr="")

    monkeypatch.setattr(composer_converter.subprocess, "run", fake_run)
    result = composer_converter.execute_plan(
        [item],
        base=str(tmp_path),
        status=status,
        dry_run=False,
        env={},
        timeout=30,
    )

    assert result.returncode == 0
    assert result.converted == 1
    assert result.failed == 0
    assert captured["command"] == [status.executable, str(source), status.settings_file]
    assert (tmp_path / "converted" / "part.smgxml").read_text(encoding="utf-8") == "synthetic output"


def test_execute_plan_reports_missing_output(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "part.CATPart"
    source.write_text("synthetic source", encoding="utf-8")
    item = SimpleNamespace(source_path="part.CATPart", target_path="converted/part.smgxml")
    status = composer_converter.ComposerConverterStatus(True, "converter.exe", "profile.xml", "", "ready")
    monkeypatch.setattr(
        composer_converter.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    result = composer_converter.execute_plan(
        [item],
        base=str(tmp_path),
        status=status,
        dry_run=False,
        env={},
        timeout=30,
    )

    assert result.returncode == 1
    assert result.converted == 0
    assert result.failed == 1
    assert "aucun fichier" in result.stderr
