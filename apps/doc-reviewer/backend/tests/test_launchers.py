"""Lanceurs Windows (`start.bat`, `_run.bat`, `_run_no_front.bat`) : pas de
detournement d'executable par le dossier courant, Python sans site-packages
utilisateur, dependances jamais resolues depuis PyPI sans empreintes."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest


APP_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_DIR.parents[1]
RUNNERS = ["_run.bat", "_run_no_front.bat"]
# Outils systeme que cmd.exe chercherait d'abord dans le dossier courant.
_SYSTEM_TOOLS = ("netstat", "findstr", "where", "powershell", "chcp")


def _code_lines(name: str) -> list[str]:
    lines = (APP_DIR / name).read_text(encoding="utf-8").splitlines()
    return [line for line in lines if line.strip() and not line.strip().upper().startswith("REM")]


@pytest.mark.parametrize("name", RUNNERS)
def test_current_directory_lookup_is_disabled(name: str) -> None:
    lines = _code_lines(name)
    assert 'set "NoDefaultCurrentDirectoryInExePath=1"' in lines[:4]


@pytest.mark.parametrize("name", RUNNERS)
def test_system_tools_are_called_by_absolute_path(name: str) -> None:
    for line in _code_lines(name):
        for tool in _SYSTEM_TOOLS:
            for match in re.finditer(rf"(?i)(?<![\\\w]){tool}(\.exe|\.com)?\b", line):
                prefix = line[: match.start()]
                assert prefix.endswith(("\\", "\\v1.0\\")), f"{name}: appel non qualifie a {tool}: {line}"


@pytest.mark.parametrize("name", RUNNERS)
def test_python_ignores_user_site_packages(name: str) -> None:
    calls = [line for line in _code_lines(name) if '"%PYTHON%"' in line]
    assert calls
    for line in calls:
        assert '"%PYTHON%" -s ' in line, line


@pytest.mark.parametrize("name", RUNNERS)
def test_dependencies_are_installed_from_the_hash_lock_only(name: str) -> None:
    code = "\n".join(_code_lines(name))
    assert "--require-hashes" in code and "requirements.lock.txt" in code
    assert "install --upgrade pip" not in code
    assert re.search(r"pip install -e \.\s*$", code, re.MULTILINE) is None
    assert "pip install --no-deps -e ." in code


@pytest.mark.parametrize("name", RUNNERS)
def test_dependency_hash_uses_direct_absolute_powershell(name: str) -> None:
    line = next(line for line in _code_lines(name) if "Get-FileHash" in line)
    assert line.startswith(r'"%SYS32%\WindowsPowerShell\v1.0\powershell.exe"')
    assert "for /f" not in line.lower()


@pytest.mark.parametrize("name", RUNNERS)
def test_dependency_hash_command_runs_in_cmd(name: str, tmp_path: Path) -> None:
    command = next(line for line in _code_lines(name) if "Get-FileHash" in line)
    script = tmp_path / "check_hash.cmd"
    hash_file = tmp_path / "dependency.hash"
    script.write_text(
        "\r\n".join(
            (
                "@echo off",
                'set "SYS32=%SystemRoot%\\System32"',
                f'set "DEPS_HASH_FILE={hash_file}"',
                f'cd /d "{APP_DIR / "backend"}"',
                command,
                'if errorlevel 1 exit /b 1',
                'set /p DEPS_HASH=<"%DEPS_HASH_FILE%"',
                'del "%DEPS_HASH_FILE%" >nul 2>nul',
                'echo HASH=%DEPS_HASH%',
            )
        ),
        encoding="ascii",
    )
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", str(script)],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert re.search(r"HASH=[0-9a-fA-F]{128}", result.stdout), result.stdout + result.stderr


def test_start_bat_uses_comspec() -> None:
    code = "\n".join(_code_lines("start.bat"))
    assert '"%ComSpec%" /k' in code


def test_packager_runs_embedded_python_without_user_site() -> None:
    source = (REPO_ROOT / "scripts" / "package_doc_reviewer.py").read_text(encoding="utf-8")
    assert '[python, "-m"' not in source
    assert source.count('[python, "-s", "-m", "pip"') >= 3
