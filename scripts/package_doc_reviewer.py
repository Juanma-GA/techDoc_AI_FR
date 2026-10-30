"""Package the doc-reviewer app into a standalone zip ready to share.

Layout of the produced archive (with `--embed-python`, default ON):

    doc-reviewer-vX.Y.Z-YYYYMMDD/
    ├── start.bat               # one-click launcher → calls apps/doc-reviewer/start.bat
    ├── LISEZ-MOI.txt           # quick-start FR for the colleague
    ├── PACKAGE_README.md       # detailed reference
    ├── apps/doc-reviewer/      # app (backend + frontend sources, no node_modules / .venv / data)
    │                           # + frontend/dist/ : the React UI served by the backend. The UI
    │                           # build is REQUIRED (there is no HTML fallback any more): it is
    │                           # built by default and a ZIP without frontend/dist/index.html is
    │                           # refused.
    ├── design-tokens/          # shared design tokens (frontend sources)
    └── python-embed/           # bundled Python 3.11.9 (Windows embeddable) with pip and the
                                # backend dependencies PRE-INSTALLED from the hash-locked
                                # backend/requirements.lock.txt (no PyPI access at first launch)

Supply chain: the embeddable Python archive and the pip wheel are verified
against pinned SHA-256 digests (downloads AND cached copies); every backend
dependency is installed with `pip --require-hashes`.

Excluded everywhere:
    - `.venv/`, `__pycache__/`, `*.pyc`     — runtime venv & bytecode
    - `data/`                               — local SQLite + uploaded PDFs (user state)
    - `tests/`, `*.pdf`                     — test suites and sample documents (may be
                                              client-proprietary: never distributed)
    - `node_modules/`, `.cache/`            — package manager + script caches
    - `.git/`, `.claude/`, IDE / cache dirs

Usage:
    python scripts/package_doc_reviewer.py
    python scripts/package_doc_reviewer.py --version 0.2.0 --out dist
    python scripts/package_doc_reviewer.py --no-build-frontend   # reuse an existing frontend/dist
    python scripts/package_doc_reviewer.py --no-embed-python     # external Python required
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
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
    "ftm_backend.egg-info",
    "doc_reviewer_backend.egg-info",
    # Test suites and their sample files are never shipped (client-proprietary
    # documents live there).
    "tests",
    # Manual verification scripts write client documents to their `outputs/`.
    "dev_tools",
}
# `.pdf`: no PDF is needed at runtime; the PDFs in the repository are client
# document samples that must never leave with the ZIP.
_EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".zip", ".pdf"}

_UI_INDEX = Path("apps") / "doc-reviewer" / "frontend" / "dist" / "index.html"


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
chcp 65001 >nul
REM One-click entry point — delegates to apps/doc-reviewer/start.bat
cd /d "%~dp0\\apps\\doc-reviewer"
call start.bat
"""


# ---- Frontend build -------------------------------------------------------

class PackagingError(RuntimeError):
    """Blocking packaging failure: no archive is produced."""


def _build_frontend(frontend_dir: Path) -> None:
    """Run `pnpm install && pnpm build` so `frontend/dist/` ends up in the zip.

    The React UI is the only UI (the backend answers 503 without it), so any
    failure is fatal: a stale `dist/` left by an earlier build is NOT reused
    silently. Raises PackagingError.
    """
    pnpm = shutil.which("pnpm")
    if pnpm is None or shutil.which("node") is None:
        raise PackagingError(
            "pnpm/node not found: cannot build the React UI. Install Node + pnpm, "
            "or re-run with --no-build-frontend if frontend/dist/ is up to date."
        )
    try:
        if (frontend_dir / "node_modules").is_dir():
            print("[frontend] node_modules present — skipping pnpm install")
        else:
            print(f"[frontend] pnpm install --frozen-lockfile ({frontend_dir})")
            subprocess.run([pnpm, "install", "--frozen-lockfile"], cwd=frontend_dir, check=True)
        print("[frontend] pnpm build")
        subprocess.run([pnpm, "build"], cwd=frontend_dir, check=True)
    except subprocess.CalledProcessError as exc:
        raise PackagingError(f"React UI build failed ({exc}).") from exc
    index = frontend_dir / "dist" / "index.html"
    if not index.is_file():
        raise PackagingError("the UI build did not produce frontend/dist/index.html.")
    n_files = sum(1 for _ in (frontend_dir / "dist").rglob("*") if _.is_file())
    print(f"[frontend] OK — {n_files} files in dist/")


def _assert_zip_has_ui(zip_path: Path, pkg_name: str) -> None:
    """Refuse an archive without the UI: without `frontend/dist/index.html` the
    delivered app only answers "Frontend non builde" (503) on the user's laptop."""
    expected = f"{pkg_name}/{_UI_INDEX.as_posix()}"
    with zipfile.ZipFile(zip_path) as zf:
        if expected not in zf.namelist():
            raise PackagingError(f"archive refused: {expected} is missing (UI not bundled).")


# ---- Embedded Python bootstrap -------------------------------------------

_EMBED_PYTHON_VERSION = "3.11.9"
_EMBED_PYTHON_ARCH = "amd64"
_EMBED_PYTHON_URL = (
    f"https://www.python.org/ftp/python/{_EMBED_PYTHON_VERSION}/"
    f"python-{_EMBED_PYTHON_VERSION}-embed-{_EMBED_PYTHON_ARCH}.zip"
)
# SHA-256 of the official python.org archive (cross-checked against the MD5
# published on https://www.python.org/downloads/release/python-3119/:
# 6d9aa08531d48fcc261ba667e2df17c4).
_EMBED_PYTHON_SHA256 = "009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b"

# pip is bootstrapped from a pinned wheel (digest from PyPI) instead of the
# unversioned, unverified https://bootstrap.pypa.io/get-pip.py.
_PIP_VERSION = "26.2.1"
_PIP_WHEEL_URL = (
    "https://files.pythonhosted.org/packages/f3/6e/"
    "1736e5b4ae2b778ef2f81c47d797de9f891d4d8acb047a24ca37a60294dd/"
    f"pip-{_PIP_VERSION}-py3-none-any.whl"
)
_PIP_WHEEL_SHA256 = "71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e"

_DOWNLOAD_TIMEOUT_S = 60

# Backend dependencies: exact versions + hashes, resolved for Windows / CPython 3.11
# (regenerate on Windows / CPython 3.11, from apps/doc-reviewer/backend, with:
#  pip-compile --generate-hashes --strip-extras --allow-unsafe --rebuild
#  --pip-args "--only-binary=:all:" --output-file requirements.lock.txt pyproject.toml
#  — binary-only, because the embeddable Python cannot build sdists).
_LOCK_FILE = Path("apps") / "doc-reviewer" / "backend" / "requirements.lock.txt"

# Marker read by apps/doc-reviewer/_run.bat: dependencies are already installed,
# the launcher must not reach PyPI at first launch.
_INSTALLED_MARKER = ".docreviewer_installed"

# `._pth` entry (relative to python-embed/) that puts the backend package on
# sys.path: the embeddable Python ignores the current directory, so the app was
# previously made importable with `pip install -e .` at first launch.
_BACKEND_PTH_ENTRY = "../apps/doc-reviewer/backend"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_sha256(path: Path, expected: str) -> None:
    actual = _sha256(path)
    if actual != expected:
        raise PackagingError(
            f"SHA-256 mismatch for {path.name}: expected {expected}, got {actual}. "
            "The file is corrupted or has been tampered with; delete it and retry "
            "(it is never reused)."
        )


def _download(url: str, dst: Path) -> None:
    if not url.startswith("https://"):
        raise PackagingError(f"refusing non-https download: {url}")
    print(f"[fetch] {url}")
    tmp = dst.with_suffix(dst.suffix + ".part")
    with urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT_S) as resp, open(tmp, "wb") as f:  # noqa: S310
        shutil.copyfileobj(resp, f)
    tmp.replace(dst)


def _fetch_verified(url: str, dst: Path, sha256: str) -> None:
    """Download `url` to `dst` unless cached, then ALWAYS verify the pinned digest
    (a poisoned cache is as dangerous as a poisoned download)."""
    if dst.exists():
        print(f"[cache] reusing {dst.name}")
    else:
        _download(url, dst)
    _verify_sha256(dst, sha256)
    print(f"[verify] {dst.name} sha256 OK")


def _prepare_embedded_python(cache_dir: Path, repo: Path) -> Path:
    """Download (or reuse) the Windows embeddable Python build, verify it,
    extract it into a fresh dir, enable site-packages, bootstrap pip from a
    pinned wheel and pre-install the hash-locked backend dependencies."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive = cache_dir / Path(_EMBED_PYTHON_URL).name
    pip_wheel = cache_dir / Path(_PIP_WHEEL_URL).name
    lock_file = repo / _LOCK_FILE
    if not lock_file.is_file():
        raise PackagingError(f"missing dependency lock file: {_LOCK_FILE}")

    _fetch_verified(_EMBED_PYTHON_URL, archive, _EMBED_PYTHON_SHA256)
    _fetch_verified(_PIP_WHEEL_URL, pip_wheel, _PIP_WHEEL_SHA256)

    work = Path(tempfile.mkdtemp(prefix="doc-reviewer-embed-"))
    print(f"[embed] extracting Python to {work}")
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(work)

    pth_files = list(work.glob("python*._pth"))
    if not pth_files:
        raise PackagingError("python*._pth not found in embed")
    pth = pth_files[0]
    lines = pth.read_text(encoding="utf-8").splitlines()
    lines = ["import site" if line.strip() == "#import site" else line for line in lines]
    if "import site" not in lines:
        lines.append("import site")
    if _BACKEND_PTH_ENTRY not in lines:
        lines.insert(0, _BACKEND_PTH_ENTRY)
    pth.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[embed] patched {pth.name} (site-packages + backend path)")

    python = str(work / "python.exe")
    print(f"[embed] bootstrapping pip {_PIP_VERSION} from the verified wheel…")
    # pip refuses to (re)install itself unless run as `python -m pip`: unpack the
    # verified pure-Python wheel into site-packages, then let that pip register
    # itself properly (RECORD, entry points) from the same local wheel.
    site_packages = work / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pip_wheel) as zf:
        zf.extractall(site_packages)
    subprocess.run(
        [python, "-s", "-m", "pip", "install", "--no-index", "--no-deps", "--force-reinstall",
         "--no-warn-script-location", "--disable-pip-version-check", str(pip_wheel)],
        check=True,
        cwd=work,
    )
    print("[embed] installing backend dependencies (--require-hashes)…")
    subprocess.run(
        [python, "-s", "-m", "pip", "install", "--require-hashes", "--no-deps",
         "--only-binary=:all:", "--no-warn-script-location", "--disable-pip-version-check",
         "-r", str(lock_file)],
        check=True,
        cwd=work,
    )
    subprocess.run(
        [python, "-s", "-m", "pip", "check", "--disable-pip-version-check"], check=True, cwd=work
    )
    (work / _INSTALLED_MARKER).write_text(
        f"requirements.lock.txt sha256={_sha256(lock_file)}\n", encoding="utf-8"
    )
    print("[embed] dependencies OK")
    return work


_LISEZ_MOI = """\
Doc Reviewer — Démarrage rapide
================================

1. Décompresser ce ZIP dans le dossier de votre choix.
2. Double-cliquer sur start.bat à la racine.

Au lancement (quelques secondes) :
  - Python 3.11 et les dépendances sont déjà inclus (aucun téléchargement).
  - La base locale est initialisée / mise à jour.
  - Le navigateur s'ouvre sur http://127.0.0.1:8003/
    (si le port 8003 est occupé : 8004, 8005 ... jusqu'à 8023 ;
    l'adresse exacte est affichée dans la fenêtre noire).

Pour arrêter : Ctrl+C dans la fenêtre noire.

Documentation détaillée : voir PACKAGE_README.md.
"""


_PACKAGE_README = """\
# Doc Reviewer — Package partageable

POC local-first qui détecte des anomalies dans des PDFs techniques
(S1000D / STE100 / règles custom / conversions d'unités) et propose des
corrections — réécrites par Mistral quand une clé API est configurée —
applicables directement dans le PDF binaire.

## Prérequis

- **Windows 10/11**.
- **Aucun pré-requis Python** : une distribution Python 3.11.9 embarquée
  est livrée dans `python-embed/`. Si tu préfères utiliser ton Python
  système, supprime ce dossier — `start.bat` se rabattra sur Python 3.11+
  trouvé dans le `PATH` (à installer depuis
  [https://www.python.org/downloads/](https://www.python.org/downloads/)).
- *(Optionnel)* Une clé API **Mistral** ([console.mistral.ai](https://console.mistral.ai))
  pour activer les suggestions IA. Sans clé, les règles déterministes
  (espaces, accents fréquents, unités) tournent quand même.

## Démarrage

1. Décompresse l'archive dans le dossier de ton choix
   (ex. `Documents/doc-reviewer/`).
2. **Double-clique sur `start.bat`** à la racine du dossier décompressé.
3. Au lancement :
   - Python 3.11.9 et les dépendances (versions et empreintes figées) sont
     déjà installés dans `python-embed/` : aucun accès à PyPI.
   - Initialisation / migration de la base SQLite locale.
4. Le navigateur s'ouvre automatiquement sur `http://127.0.0.1:8003/`
   (port suivant libre jusqu'à 8023 si 8003 est occupé ; l'adresse est
   affichée dans la console).

Pour arrêter le serveur : ferme la fenêtre `cmd` ou fais `Ctrl+C` dedans.

## Configurer Mistral (optionnel)

1. Onglet **Paramètres** → **Configuration Mistral**.
2. Colle ta clé API, **Sauvegarder**, puis **Tester la connexion**.
3. La clé est stockée localement (SQLite, dans `apps/doc-reviewer/backend/data/`).

Sans Mistral configuré, les règles dites « qualitatives » (voix passive,
gérondif, première personne, phrase trop longue, scan custom) sont
silencieusement skippées — seules les règles mécaniques (doubles espaces,
ponctuation, accents fréquents, conversions d'unités, règles regex
définies par toi) génèrent des suggestions.

## Workflow

1. **Documents** → glisse un ou plusieurs PDFs dans la dropzone (multi-sélection acceptée).
2. L'analyse démarre **automatiquement** : badge ⚙ *en cours d'analyse*
   → ✓ *analysée*.
3. Clique **🔍 Corriger** sur un document.
4. Le viewer affiche la page courante du PDF avec les anomalies
   surlignées (overlays cliquables) ; le panneau de droite liste toutes
   les suggestions du document.
5. Pour chaque suggestion, choisis :
   - **✓ Accepter & appliquer** : Mistral / la règle déterministe a déjà
     préparé la correction → le PDF binaire est édité in-place
     (versionnage `v0.pdf` → `v1.pdf` → `v2.pdf`…).
   - **✎ Modifier** : ajuste le texte proposé dans une textarea avant
     d'accepter (utile pour les reformulations IA).
   - **✗ Rejeter** : la suggestion disparaît.
6. Sur une suggestion appliquée, le bouton **↶ Annuler la correction**
   apparaît : un clic ramène le PDF à la version d'avant ce patch (et
   ré-active toutes les corrections postérieures dans la cascade).
7. **▶ Lancer l'analyse** : relance l'analyse sur la version courante
   du PDF (post-édition), pas sur l'original. Idéal pour itérer.
8. **⬇ Exporter le PDF édité** : télécharge la version courante.

## Personnaliser les règles

Tout est dans **Paramètres** :

- **Configuration Mistral** : clé API, base URL, modèle (`mistral-small-latest` par défaut).
- **Consignes IA personnalisées** : zone de texte libre — tes consignes
  en langage naturel sont passées à Mistral à chaque analyse, en plus
  des règles formelles. Exemple :
  *« Pas de mot en complètes majuscules, pas d'oubli d'accents,
  pas d'espace entre les parenthèses. »*
- **Règles S1000D built-in** : 6 règles activables individuellement
  (voix passive STE100, première personne, gérondif procédural,
  phrase > 25 mots, format des warnings, doubles espaces).
- **Règles custom** : crée tes propres règles via le formulaire :
  - `term_replace` — remplacement littéral case-insensitive.
  - `regex_replace` — regex avec groupes de capture (`\\1`, `\\2`, …).
  - `regex_flag` — signaler sans proposer (utile pour flags génériques
    que Mistral reformulera).
  - `case_capitalize` — mots en MAJUSCULES → Capitalize.
  - `accent_fix` — mots français sans diacritiques → version accentuée
    (map maintenu côté backend).
  - 3 règles sont **seedées par défaut** au premier lancement
    (ponctuation, MAJUSCULES, accents) — tu peux les éditer ou les
    supprimer.
- **Système d'unités cible** : `auto` / `metric` / `imperial` —
  détermine vers quel système les conversions cm/mm/m ↔ in/ft, kg ↔ lb
  vont être proposées.

## Désinstaller

Il suffit de supprimer le dossier décompressé. Toute la donnée
(DB SQLite, PDFs uploadés, snapshots versionnés) est dedans :
`apps/doc-reviewer/backend/data/`.

## Données

Aucune donnée ne quitte ta machine **sauf si Mistral est configuré** :
dans ce cas, le **texte** des pages PDF (max 30 premières pages par
analyse) et tes consignes sont envoyés à `api.mistral.ai` pendant
l'analyse. Le binaire des PDFs reste local.

Aucune télémétrie, aucun cookie, aucune analytics.

## Limitations connues

- Édition PDF **best-effort** : kerning, ligatures et justification
  ne sont pas préservés. Le rendu peut visuellement se dégrader sur les
  paragraphes denses. Le bouton **↶ Annuler la correction** est toujours
  disponible.
- Polices manquantes → fallback Helvetica.
- PDFs **signés numériquement** refusés à l'upload (la signature serait
  invalidée par toute édition).
- PDFs **scannés sans couche texte** : pas de détection (pas d'OCR
  embarqué dans ce POC).
- Limite **20 PDFs** par batch d'upload, **30 premières pages** par
  PDF traitées par Mistral.

## Support

Cette app est un POC interne. Pour tout retour, contacte le porteur du POC.
"""


def _walk_sources(repo: Path, source_paths: list[str]) -> list[tuple[Path, Path]]:
    out: list[tuple[Path, Path]] = []
    for src_rel in source_paths:
        src_root = repo / src_rel
        if not src_root.is_dir():
            raise PackagingError(f"missing source directory: {src_rel}")
        for path in sorted(src_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(repo)
            if _should_skip(rel):
                continue
            out.append((path, rel))
    return out


def _write_zip(
    zip_path: Path, pkg_name: str, files: list[tuple[Path, Path]], embed_dir: Path | None
) -> None:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Package doc-reviewer into a standalone zip.",
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
        help="Bundle a Windows embeddable Python with the backend dependencies "
             "pre-installed (hash-locked) so the colleague needs no prerequisites "
             "and no PyPI access (default: enabled). Use --no-embed-python to "
             "require Python 3.11+ on the user's PATH instead.",
    )
    parser.add_argument(
        "--build-frontend",
        dest="build_frontend",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run `pnpm install --frozen-lockfile && pnpm build` before zipping "
             "(default: enabled). The React UI is the only UI: a failed build "
             "aborts the packaging. --no-build-frontend reuses the existing "
             "frontend/dist/ (it must contain index.html).",
    )
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parent.parent
    out_dir: Path = (repo / args.out).resolve() if not args.out.is_absolute() else args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.date.today().strftime("%Y%m%d")
    pkg_name = f"doc-reviewer-v{args.version}-{stamp}"
    zip_path = out_dir / f"{pkg_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    print(f"[package] building {zip_path}")

    embed_dir: Path | None = None
    try:
        frontend_dir = repo / "apps" / "doc-reviewer" / "frontend"
        if args.build_frontend:
            _build_frontend(frontend_dir)
        else:
            print("[frontend] build skipped (--no-build-frontend) — reusing frontend/dist/")
        if not (repo / _UI_INDEX).is_file():
            raise PackagingError(
                f"{_UI_INDEX.as_posix()} missing: the React UI is required "
                "(the backend only answers 503 without it)."
            )

        files = _walk_sources(repo, ["apps/doc-reviewer", "design-tokens"])
        if args.embed_python:
            embed_dir = _prepare_embedded_python(out_dir / ".cache", repo)
        _write_zip(zip_path, pkg_name, files, embed_dir)
        _assert_zip_has_ui(zip_path, pkg_name)
    except (PackagingError, subprocess.CalledProcessError, OSError) as exc:
        if zip_path.exists():
            zip_path.unlink()
        print(f"[error] packaging failed, no archive produced: {exc}", file=sys.stderr)
        return 2
    finally:
        if embed_dir is not None:
            shutil.rmtree(embed_dir, ignore_errors=True)

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"[package] OK -> {zip_path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())