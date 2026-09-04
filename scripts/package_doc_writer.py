"""Package the doc-writer app into a standalone zip ready to share.

Layout of the produced archive (with `--embed-python`, default ON):

    doc-writer-vX.Y.Z-YYYYMMDD/
    ├── start.bat               # one-click launcher → calls apps/doc-writer/start.bat
    ├── LISEZ-MOI.txt           # quick-start FR for the colleague
    ├── PACKAGE_README.md       # detailed reference
    ├── apps/doc-writer/        # full app (backend + frontend sources, no node_modules / .venv / data)
    │   └── frontend/dist/      # built React UI (only if pnpm + node are available distributor-side)
    ├── design-tokens/          # design-token assets used by the React build
    └── python-embed/           # bundled Python 3.11 (Windows embeddable + bootstrapped pip)

Excluded everywhere:
    - `.venv/`, `__pycache__/`, `*.pyc`     — runtime venv & bytecode (recreated at first launch)
    - `data/`                               — local SQLite + uploaded docs (user state)
    - `node_modules/`, `.cache/`            — package manager + script caches
    - `.git/`, `.claude/`, IDE / cache dirs

Usage:
    python scripts/package_doc_writer.py
    python scripts/package_doc_writer.py --version 0.2.0 --out dist
    python scripts/package_doc_writer.py --no-embed-python  # external Python required
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
    "doc_writer_backend.egg-info",
}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".zip"}


def _should_skip(rel: Path) -> bool:
    if any(part in _EXCLUDED_DIRS for part in rel.parts):
        return True
    if rel.suffix.lower() in _EXCLUDED_SUFFIXES:
        return True
    if rel.name.startswith(".") and rel.name not in {".env.example"}:
        return True
    return False


_ROOT_LAUNCHER = """\
@echo off
REM One-click entry point - delegates to apps/doc-writer/start.bat
cd /d "%~dp0\\apps\\doc-writer"
call start.bat
"""


# ---- Frontend build -------------------------------------------------------

def _build_frontend(frontend_dir: Path) -> bool:
    """Build `frontend/dist/` so the React UI ends up in the zip.

    `pnpm install` is run ONLY when `node_modules/` is absent: behind a TLS
    intercepting proxy an "up-to-date" install retries every package for minutes
    and then fails, which used to skip the build entirely. `pnpm build` alone
    works fully offline when node_modules is present.

    Returns True if a fresh build produced dist/. Returns False on any failure
    (pnpm/node absent, build error) — but a pre-existing `frontend/dist/` is
    left untouched and still gets bundled by the source walk, so the recipient
    keeps the last good UI instead of falling back to Swagger.
    """
    dist = frontend_dir / "dist"
    has_existing_dist = (dist / "index.html").is_file()

    pnpm = shutil.which("pnpm")
    if pnpm is None or shutil.which("node") is None:
        print("[frontend] pnpm/node not found — skipping build")
        if has_existing_dist:
            print("           bundling the existing frontend/dist/ as-is")
        else:
            print("           (recipient sees only Swagger UI; install pnpm+node to bundle React UI)")
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
        if has_existing_dist:
            print(f"[frontend] build failed ({exc}) — keeping existing frontend/dist/")
        else:
            print(f"[frontend] build failed ({exc}) — NO dist/ to bundle, recipient sees only Swagger UI")
        return False
    if not dist.is_dir():
        print("[frontend] no dist/ produced — skipping")
        return False
    n_files = sum(1 for _ in dist.rglob("*") if _.is_file())
    print(f"[frontend] OK — {n_files} files in dist/")
    return True


# ---- Embedded Python bootstrap -------------------------------------------

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
    else:
        print(f"[cache] reusing {archive.name}")
    if not get_pip.exists():
        _download(_GET_PIP_URL, get_pip)
    else:
        print("[cache] reusing get-pip.py")

    work = Path(tempfile.mkdtemp(prefix="doc-writer-embed-"))
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
    print(f"[embed] patched {pth.name} (site-packages enabled)")

    print("[embed] bootstrapping pip...")
    subprocess.run(
        [str(work / "python.exe"), str(get_pip), "--no-warn-script-location"],
        check=True,
        cwd=work,
    )
    print("[embed] pip OK")
    return work


_LISEZ_MOI = """\
doc-writer — Démarrage rapide
==============================

1. Décompresser ce ZIP dans le dossier de votre choix.
2. Double-cliquer sur start.bat à la racine.

Au premier lancement (1 à 3 minutes) :
  - Python est détecté ou auto-installé (sans droits admin).
  - Les dépendances Python sont installées.
  - Le navigateur s'ouvre sur http://127.0.0.1:8002/

Lancements suivants : ~5 secondes.

Pour arrêter : Ctrl+C dans la fenêtre noire.

Documentation détaillée : voir PACKAGE_README.md.
"""


_PACKAGE_README = """\
# doc-writer — Package partageable

POC local-first qui permet de générer du contenu rédactionnel (markdown
avec citations) à partir d'un prompt utilisateur et de documents uploadés
(PDF, DOCX, XLSX, TXT, MD), via Mistral en RAG streaming.

## Prérequis

- **Windows 10/11**.
- **Aucun pré-requis Python** : une distribution Python 3.11.9 embarquée
  est livrée dans `python-embed/`. Si tu préfères utiliser ton Python
  système, supprime ce dossier — `start.bat` se rabattra sur Python 3.11+
  trouvé dans le `PATH` (à installer depuis
  [https://www.python.org/downloads/](https://www.python.org/downloads/)).
- **Clé API Mistral** ([console.mistral.ai](https://console.mistral.ai))
  obligatoire pour la génération et l'indexation RAG.

## Démarrage

1. Décompresse l'archive dans le dossier de ton choix
   (ex. `Documents/doc-writer/`).
2. **Double-clique sur `start.bat`** à la racine du dossier décompressé.
3. Au **premier lancement** (1 à 3 minutes) :
   - Création d'un environnement Python virtuel local
     (`apps/doc-writer/backend/.venv/`).
   - Installation des dépendances Python (FastAPI, PyMuPDF, python-docx,
     openpyxl, numpy, structlog, etc.).
   - Initialisation de la base SQLite locale.
4. Le navigateur s'ouvre automatiquement sur `http://127.0.0.1:8002/`.

Aux lancements suivants : **~5 secondes**.

Pour arrêter le serveur : ferme la fenêtre `cmd` ou fais `Ctrl+C` dedans.

## Configurer Mistral

1. Onglet **Paramètres** → renseigner la clé API Mistral.
2. Cliquer **Tester la connexion** pour valider.
3. La clé est stockée localement (SQLite, dans `apps/doc-writer/backend/data/`).

## Workflow

1. **Documents** → glisse PDF / DOCX / XLSX / TXT / MD dans la dropzone.
   L'indexation Mistral tourne automatiquement.
2. **Génération** → sélectionne tes documents, écris un brief, clique
   **Générer**. Le contenu se streame en markdown avec citations
   `[nom_fichier]`.
3. **Sessions** : historique de toutes tes générations, relisibles.

## Désinstaller

Il suffit de supprimer le dossier décompressé. Toute la donnée (DB
SQLite, fichiers uploadés) est dans `apps/doc-writer/backend/data/`.

## Données

Aucune donnée ne quitte ta machine **sauf via Mistral** : le texte
extrait des documents (chunks) et tes briefs sont envoyés à
`api.mistral.ai` pour l'indexation et la génération. Les binaires des
fichiers restent locaux.

Aucune télémétrie, aucun cookie, aucune analytics.

## Support

Cette app est un POC interne. Pour tout retour, contacte le porteur du POC.
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
        description="Package doc-writer into a standalone zip.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--version", default="0.1.0",
                        help="Version label for the archive (default: 0.1.0).")
    parser.add_argument("--out", type=Path, default=Path("dist"),
                        help="Output directory relative to the repo root (default: dist).")
    parser.add_argument(
        "--embed-python",
        dest="embed_python",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Bundle a Windows embeddable Python in the archive so the colleague "
             "needs no prerequisites (default: enabled). Use --no-embed-python "
             "to skip and require Python 3.11+ on the user's PATH.",
    )
    parser.add_argument(
        "--build-frontend",
        dest="build_frontend",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run `pnpm install && pnpm build` before zipping so the React UI "
             "is included (default: enabled, skipped gracefully if pnpm/node "
             "are absent).",
    )
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parent.parent
    out_dir: Path = (repo / args.out).resolve() if not args.out.is_absolute() else args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.date.today().strftime("%Y%m%d")
    pkg_name = f"doc-writer-v{args.version}-{stamp}"
    zip_path = out_dir / f"{pkg_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    print(f"[package] building {zip_path.relative_to(repo)}")

    if args.build_frontend:
        _build_frontend(repo / "apps" / "doc-writer" / "frontend")

    sources = ["apps/doc-writer", "design-tokens"]
    files = _walk_sources(repo, sources)

    embed_dir: Path | None = None
    if args.embed_python:
        try:
            embed_dir = _prepare_embedded_python(out_dir / ".cache")
        except Exception as exc:  # noqa: BLE001
            print(f"[error] embedded Python preparation failed: {exc}", file=sys.stderr)
            print("[hint] re-run with --no-embed-python to skip the bundled Python",
                  file=sys.stderr)
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
