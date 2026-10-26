"""Package the Image Processor app into a standalone Windows zip.

The archive contains separate Python runtimes for PaddleOCR and LaMa. Dependency
installation and model downloads occur on first use; inference remains local.

Layout of the produced archive (with `--embed-python`, default ON):

    image-processor-vX.Y.Z-YYYYMMDD/
    ├── start.bat               # one-click launcher → calls apps/<poc>/start.bat
    ├── LISEZ-MOI.txt           # quick-start FR for the colleague
    ├── PACKAGE_README.md       # detailed reference
    ├── apps/<poc>/             # full app (backend + frontend sources, no node_modules / .venv / data)
    │   └── frontend/dist/      # built React UI (only if pnpm + node are available distributor-side)
    ├── design-tokens/          # design-token assets used by the React build
    ├── python-embed/           # bundled Python 3.11 for PaddleOCR
    └── python-embed-lama/      # bundled Python 3.11 for LaMa

Usage:
    python scripts/package_image-processor.py
    python scripts/package_image-processor.py --version 0.2.0 --out dist
    python scripts/package_image-processor.py --no-embed-python
"""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from image_processor_package_runtime import prepare_embedded_python

# =====================================================================
# Variables a adapter par POC :
APP_NAME = "Image Processor"
APP_SLUG = "image-processor"      # nom du dossier sous apps/
EMBED_PREFIX = "image_processor"
_OCR_PYTHON_VERSION = "3.11.9"
_LAMA_PYTHON_VERSION = "3.11.9"
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
}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".zip"}


def _should_skip(rel: Path) -> bool:
    if any(part in _EXCLUDED_DIRS or part.endswith(".egg-info") for part in rel.parts):
        return True
    if rel.suffix.lower() in _EXCLUDED_SUFFIXES:
        return True
    if rel.name.startswith(".") and rel.name not in {".env.example"}:
        return True
    return False


_ROOT_LAUNCHER = f"""\
@echo off
REM One-click entry point - delegates to apps/{APP_SLUG}/start.bat
cd /d "%~dp0\\apps\\{APP_SLUG}"
call start.bat
"""


def _build_frontend(frontend_dir: Path) -> bool:
    pnpm = shutil.which("pnpm")
    if pnpm is None or shutil.which("node") is None:
        print("[frontend] pnpm/node not found — skipping build")
        return False
    try:
        if (frontend_dir / "node_modules").is_dir():
            print("[frontend] node_modules present — skipping pnpm install")
        else:
            print(f"[frontend] pnpm install ({frontend_dir})")
            subprocess.run([pnpm, "install"], cwd=frontend_dir, check=True)
        print("[frontend] pnpm build")
        subprocess.run([pnpm, "build"], cwd=frontend_dir, check=True)
    except subprocess.CalledProcessError as exc:
        if (frontend_dir / "dist" / "index.html").is_file():
            print(f"[frontend] build failed ({exc}) — keeping existing frontend/dist/")
        else:
            print(f"[frontend] build failed ({exc}) — NO dist/ to bundle")
        return False
    dist = frontend_dir / "dist"
    if not dist.is_dir():
        return False
    n = sum(1 for _ in dist.rglob("*") if _.is_file())
    print(f"[frontend] OK — {n} files in dist/")
    return True


_LISEZ_MOI = f"""\
{APP_NAME} — Démarrage rapide
==============================

1. Décompresser ce ZIP dans le dossier de votre choix.
2. Double-cliquer sur start.bat à la racine.

Au premier lancement : dépendances installées, modèles téléchargés au besoin,
navigateur ouvert automatiquement. L'inférence OCR et LaMa reste locale.

Lancements suivants : ~5 secondes.

Pour arrêter : Ctrl+C dans la fenêtre noire.

Documentation détaillée : voir PACKAGE_README.md.
"""


_PACKAGE_README = f"""\
# {APP_NAME} — Package partageable

L'application lance deux services locaux : PaddleOCR sous Python {_OCR_PYTHON_VERSION}
et LaMa sous Python {_LAMA_PYTHON_VERSION}. Les modèles peuvent être téléchargés
au premier usage ; l'inférence d'image reste locale.

Consultez `apps/{APP_SLUG}/README.md` pour le workflow, les prérequis et les limites.
"""


def _walk_sources(repo: Path, source_paths: list[str]) -> list[tuple[Path, Path]]:
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
            if _should_skip(rel):
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
    # Standard : le package sort TOUJOURS dans apps/<poc>/dist/ (pas la racine).
    parser.add_argument("--out", type=Path, default=Path(f"apps/{APP_SLUG}/dist"))
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
        default=True,
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

    sources = [f"apps/{APP_SLUG}", "design-tokens"]
    files = _walk_sources(repo, sources)

    embed_dirs: list[tuple[str, Path]] = []
    if args.embed_python:
        try:
            cache_dir = out_dir / ".cache"
            embed_dirs.append(
                (
                    "python-embed",
                    prepare_embedded_python(cache_dir, _OCR_PYTHON_VERSION, EMBED_PREFIX),
                )
            )
            embed_dirs.append(
                (
                    "python-embed-lama",
                    prepare_embedded_python(cache_dir, _LAMA_PYTHON_VERSION, f"{EMBED_PREFIX}_lama"),
                )
            )
        except Exception as exc:
            for _, runtime_dir in embed_dirs:
                shutil.rmtree(runtime_dir, ignore_errors=True)
            print(f"[error] embedded Python preparation failed: {exc}", file=sys.stderr)
            return 2

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.writestr(f"{pkg_name}/start.bat", _ROOT_LAUNCHER)
            zf.writestr(f"{pkg_name}/LISEZ-MOI.txt", _LISEZ_MOI)
            zf.writestr(f"{pkg_name}/PACKAGE_README.md", _PACKAGE_README)
            for path, rel in files:
                zf.write(path, f"{pkg_name}/{rel.as_posix()}")
            for runtime_name, runtime_dir in embed_dirs:
                for path in sorted(runtime_dir.rglob("*")):
                    if not path.is_file():
                        continue
                    rel = path.relative_to(runtime_dir)
                    if any(part in {"__pycache__"} for part in rel.parts):
                        continue
                    zf.write(path, f"{pkg_name}/{runtime_name}/{rel.as_posix()}")
    finally:
        for _, runtime_dir in embed_dirs:
            shutil.rmtree(runtime_dir, ignore_errors=True)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"[package] OK -> {zip_path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
