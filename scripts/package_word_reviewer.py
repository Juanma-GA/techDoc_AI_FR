"""Package the TEMPLATE app into a standalone zip ready to share.

This is the canonical packaging script for new POCs. To instantiate :

    cp scripts/package_TEMPLATE.py scripts/package_<poc>.py

Then replace `TEMPLATE`/`template` with the new POC name throughout
(name, default --out, sources list, embed prefix, LISEZ-MOI/PACKAGE_README).

Layout of the produced archive (with `--embed-python`, default ON):

    TEMPLATE-vX.Y.Z-YYYYMMDD/
    ├── start.bat               # one-click launcher → calls apps/<poc>/start.bat
    ├── LISEZ-MOI.txt           # quick-start FR for the colleague
    ├── PACKAGE_README.md       # detailed reference
    ├── apps/<poc>/             # full app (backend + frontend sources, no node_modules / .venv / data)
    │                           # frontend/dist NOT shipped by default -> main.py serves backend preview.html
    │                           # (no Node needed). Pass --build-frontend once React reaches parity.
    ├── design-tokens/          # design-token assets used by the React build
    └── python-embed/           # bundled Python 3.11 (Windows embeddable + bootstrapped pip)

Usage:
    python scripts/package_TEMPLATE.py
    python scripts/package_TEMPLATE.py --version 0.2.0 --out dist
    python scripts/package_TEMPLATE.py --no-embed-python
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


# =====================================================================
# Variables a adapter par POC :
APP_NAME = "Word-Reviewer"
APP_SLUG = "word-reviewer"      # nom du dossier sous apps/
EMBED_PREFIX = "word_reviewer"   # prefixe du dossier temp pour l'embed Python
# =====================================================================


_EXCLUDED_DIRS = {
    ".venv",
    "__pycache__",
    "data",
    "node_modules",
    ".cache",
    ".git",
    ".claude",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "playwright-report",
    "test-results",
    f"{APP_SLUG.replace('-', '_')}_backend.egg-info",
}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".zip"}


def _should_skip(rel: Path, include_frontend_dist: bool = False) -> bool:
    if any(part in _EXCLUDED_DIRS for part in rel.parts):
        return True
    if rel.suffix.lower() in _EXCLUDED_SUFFIXES:
        return True
    if rel.name.startswith(".") and rel.name not in {".env.example"}:
        return True
    # Sans --build-frontend, on NE livre PAS frontend/dist : l'UI est le
    # preview.html complet du backend (aucun Node requis). Un dist (potentiellement
    # un stub React) ferait servir main.py la SPA au lieu du preview.
    parts = set(rel.parts)
    if not include_frontend_dist and "frontend" in parts and "dist" in parts:
        return True
    return False


_ROOT_LAUNCHER = f"""\
@echo off
REM One-click entry point - delegates to apps/{APP_SLUG}/start.bat
cd /d "%~dp0\\apps\\{APP_SLUG}"
call start.bat
"""


def _build_frontend(frontend_dir: Path) -> bool:
    if shutil.which("pnpm") is None or shutil.which("node") is None:
        print("[frontend] pnpm/node not found — skipping build")
        return False
    print(f"[frontend] pnpm install ({frontend_dir})")
    try:
        subprocess.run("pnpm install", cwd=frontend_dir, check=True, shell=True)
        print("[frontend] pnpm build")
        subprocess.run("pnpm build", cwd=frontend_dir, check=True, shell=True)
    except subprocess.CalledProcessError as exc:
        print(f"[frontend] build failed ({exc}) — continuing without dist/")
        return False
    dist = frontend_dir / "dist"
    if not dist.is_dir():
        return False
    n = sum(1 for _ in dist.rglob("*") if _.is_file())
    print(f"[frontend] OK — {n} files in dist/")
    return True


_EMBED_PYTHON_VERSION = "3.11.9"
_EMBED_PYTHON_ARCH = "amd64"
_EMBED_PYTHON_URL = (
    f"https://www.python.org/ftp/python/{_EMBED_PYTHON_VERSION}/"
    f"python-{_EMBED_PYTHON_VERSION}-embed-{_EMBED_PYTHON_ARCH}.zip"
)
_GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
_DOWNLOAD_TIMEOUT_S = 60


def _download(url: str, dst: Path) -> None:
    print(f"[fetch] {url}")
    with urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT_S) as resp, open(dst, "wb") as f:
        shutil.copyfileobj(resp, f)


def _prepare_embedded_python(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive = cache_dir / Path(_EMBED_PYTHON_URL).name
    get_pip = cache_dir / "get-pip.py"

    if not archive.exists():
        _download(_EMBED_PYTHON_URL, archive)
    if not get_pip.exists():
        _download(_GET_PIP_URL, get_pip)

    work = Path(tempfile.mkdtemp(prefix=f"{EMBED_PREFIX}-embed-"))
    print(f"[embed] extracting Python to {work}")
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(work)

    pth_files = list(work.glob("python*._pth"))
    if not pth_files:
        raise RuntimeError("python*._pth not found in embed")
    pth = pth_files[0]
    content = pth.read_text(encoding="utf-8")
    if "#import site" in content:
        content = content.replace("#import site", "import site")
    elif "import site" not in content:
        content += "\nimport site\n"
    pth.write_text(content, encoding="utf-8")

    print("[embed] bootstrapping pip...")
    subprocess.run(
        [str(work / "python.exe"), str(get_pip), "--no-warn-script-location"],
        check=True,
        cwd=work,
    )
    print("[embed] pip OK")
    return work


_LISEZ_MOI = f"""\
{APP_NAME} — Démarrage rapide
==============================

1. Décompresser ce ZIP dans le dossier de votre choix.
2. Double-cliquer sur start.bat à la racine.

Au premier lancement (1 à 3 minutes) : Python détecté ou auto-installé,
dépendances installées, navigateur ouvert automatiquement.

Lancements suivants : ~5 secondes.

Pour arrêter : Ctrl+C dans la fenêtre noire.

Documentation détaillée : voir PACKAGE_README.md.
"""


_PACKAGE_README = f"""\
# {APP_NAME} — Package partageable

POC local-first. À compléter par POC : objectif, prérequis, workflow,
configuration. Voir scripts/package_{APP_SLUG}.py pour un exemple.
"""


def _walk_sources(
    repo: Path, source_paths: list[str], include_frontend_dist: bool = False
) -> list[tuple[Path, Path]]:
    out: list[tuple[Path, Path]] = []
    for src_rel in source_paths:
        src_root = repo / src_rel
        if not src_root.is_dir():
            print(f"[warn] missing source: {src_rel}", file=sys.stderr)
            continue
        for path in sorted(src_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(repo)
            if _should_skip(rel, include_frontend_dist):
                continue
            out.append((path, rel))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=f"Package {APP_NAME} into a standalone zip.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--version", default="0.1.0")
    parser.add_argument("--out", type=Path, default=Path("dist"))
    parser.add_argument(
        "--embed-python",
        dest="embed_python",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--build-frontend",
        dest="build_frontend",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Build et embarque la SPA React. Par defaut OFF : on livre le "
             "preview.html du backend (aucun Node requis). A activer seulement "
             "quand le React atteint la parite avec le preview.",
    )
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parent.parent
    out_dir: Path = (repo / args.out).resolve() if not args.out.is_absolute() else args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.date.today().strftime("%Y%m%d")
    pkg_name = f"{APP_NAME}-v{args.version}-{stamp}"
    zip_path = out_dir / f"{pkg_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    print(f"[package] building {zip_path.relative_to(repo)}")

    if args.build_frontend:
        _build_frontend(repo / "apps" / APP_SLUG / "frontend")
    else:
        print("[frontend] ignore - on livre le preview.html du backend (aucun Node "
              "requis). Passe --build-frontend une fois le React a parite.")

    sources = [f"apps/{APP_SLUG}", "design-tokens"]
    files = _walk_sources(repo, sources, include_frontend_dist=args.build_frontend)

    embed_dir: Path | None = None
    if args.embed_python:
        try:
            embed_dir = _prepare_embedded_python(out_dir / ".cache")
        except Exception as exc:  # noqa: BLE001
            print(f"[error] embedded Python preparation failed: {exc}", file=sys.stderr)
            return 2

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(f"{pkg_name}/start.bat", _ROOT_LAUNCHER)
        zf.writestr(f"{pkg_name}/LISEZ-MOI.txt", _LISEZ_MOI)
        zf.writestr(f"{pkg_name}/PACKAGE_README.md", _PACKAGE_README)
        for path, rel in files:
            zf.write(path, f"{pkg_name}/{rel.as_posix()}")
        if embed_dir is not None:
            for path in sorted(embed_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(embed_dir)
                if any(part in {"__pycache__"} for part in rel.parts):
                    continue
                zf.write(path, f"{pkg_name}/python-embed/{rel.as_posix()}")

    if embed_dir is not None:
        shutil.rmtree(embed_dir, ignore_errors=True)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"[package] OK -> {zip_path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
