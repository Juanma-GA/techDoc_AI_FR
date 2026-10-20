"""Script de packaging (`scripts/package_doc_reviewer.py`) : integrite de la
chaine d'approvisionnement, refus d'un ZIP sans UI, contenu livre."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "package_doc_reviewer.py"
LOCK_FILE = REPO_ROOT / "apps" / "doc-reviewer" / "backend" / "requirements.lock.txt"


@pytest.fixture(scope="module")
def pkg() -> ModuleType:
    spec = importlib.util.spec_from_file_location("package_doc_reviewer", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_quick_start_texts_announce_the_real_port(pkg: ModuleType) -> None:
    for text in (pkg._LISEZ_MOI, pkg._PACKAGE_README):
        assert "8001" not in text
        assert "http://127.0.0.1:8003/" in text
        assert "8023" in text


def test_docstring_no_longer_claims_the_ui_build_is_optional(pkg: ModuleType) -> None:
    doc = pkg.__doc__ or ""
    assert "preview.html" not in doc
    assert "frontend/dist" in doc and "REQUIRED" in doc


def test_build_frontend_is_on_by_default(
    pkg: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[Path] = []

    def _fake_build(frontend_dir: Path) -> None:
        calls.append(frontend_dir)
        raise pkg.PackagingError("stop")

    monkeypatch.setattr(pkg, "_build_frontend", _fake_build)
    assert pkg.main(["--no-embed-python", "--out", str(tmp_path)]) == 2
    assert len(calls) == 1


def test_failed_frontend_build_produces_no_zip(
    pkg: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _failing_build(_frontend_dir: Path) -> None:
        raise pkg.PackagingError("React UI build failed")

    monkeypatch.setattr(pkg, "_build_frontend", _failing_build)
    assert pkg.main(["--no-embed-python", "--out", str(tmp_path)]) == 2
    assert list(tmp_path.glob("*.zip")) == []


def test_missing_dist_index_is_refused_without_build(
    pkg: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pkg, "_UI_INDEX", Path("apps") / "doc-reviewer" / "frontend" / "no-dist" / "index.html")
    assert pkg.main(["--no-embed-python", "--no-build-frontend", "--out", str(tmp_path)]) == 2
    assert list(tmp_path.glob("*.zip")) == []


def test_build_frontend_fails_loudly_without_pnpm(
    pkg: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pkg.shutil, "which", lambda _name: None)
    with pytest.raises(pkg.PackagingError):
        pkg._build_frontend(tmp_path)


def test_zip_without_ui_is_refused(pkg: ModuleType, tmp_path: Path) -> None:
    archive = tmp_path / "pkg.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("doc-reviewer-v1/start.bat", "@echo off")
    with pytest.raises(pkg.PackagingError, match="index.html"):
        pkg._assert_zip_has_ui(archive, "doc-reviewer-v1")

    with zipfile.ZipFile(archive, "a") as zf:
        zf.writestr("doc-reviewer-v1/apps/doc-reviewer/frontend/dist/index.html", "<html>")
    pkg._assert_zip_has_ui(archive, "doc-reviewer-v1")


def test_shipped_files_exclude_tests_and_client_pdfs(pkg: ModuleType) -> None:
    assert pkg._should_skip(Path("apps/doc-reviewer/79-30-02-01_test_erreur.pdf"))
    assert pkg._should_skip(Path("apps/doc-reviewer/backend/tests/backend_only_tests/outputs/original.pdf"))
    assert pkg._should_skip(Path("apps/doc-reviewer/backend/tests/test_health.py"))
    assert pkg._should_skip(Path("apps/doc-reviewer/backend/data/doc-reviewer.db"))
    assert pkg._should_skip(Path("apps/doc-reviewer/backend/.env"))
    assert not pkg._should_skip(Path("apps/doc-reviewer/frontend/dist/index.html"))
    assert not pkg._should_skip(Path("apps/doc-reviewer/backend/requirements.lock.txt"))
    assert not pkg._should_skip(Path("apps/doc-reviewer/backend/.env.example"))


def test_tampered_cached_download_is_rejected(pkg: ModuleType, tmp_path: Path) -> None:
    cached = tmp_path / "python-3.11.9-embed-amd64.zip"
    cached.write_bytes(b"not the official archive")

    def _no_download(*_args: object) -> None:
        raise AssertionError("a cached file must be verified, not re-downloaded")

    original = pkg._download
    pkg._download = _no_download
    try:
        with pytest.raises(pkg.PackagingError, match="SHA-256 mismatch"):
            pkg._fetch_verified(pkg._EMBED_PYTHON_URL, cached, pkg._EMBED_PYTHON_SHA256)
    finally:
        pkg._download = original


def test_downloads_are_https_only_and_pinned(pkg: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(pkg.PackagingError):
        pkg._download("http://www.python.org/ftp/python/x.zip", tmp_path / "x.zip")
    assert len(pkg._EMBED_PYTHON_SHA256) == 64
    assert len(pkg._PIP_WHEEL_SHA256) == 64
    assert not hasattr(pkg, "_GET_PIP_URL")


def test_dependency_lock_pins_every_package_with_hashes() -> None:
    requirements: list[str] = []
    options: list[str] = []
    current: list[str] = []
    for raw in LOCK_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not current and line.startswith("--"):
            options.append(line)
            continue
        current.append(line)
        if not line.endswith("\\"):
            requirements.append(" ".join(current))
            current = []
    # Python embarque : aucune compilation de sdist possible -> roues uniquement.
    assert "--only-binary :all:" in options
    assert requirements
    for requirement in requirements:
        name = requirement.split()[0]
        assert "==" in name, requirement
        assert "--hash=sha256:" in requirement, name
