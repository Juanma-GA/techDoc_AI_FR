"""Package the pdf-reviewer app into a standalone zip ready to share.

Layout of the produced archive (with `--embed-python`, default ON):

    pdf-reviewer-vX.Y.Z-YYYYMMDD/
    ├── start.bat               # one-click launcher → calls apps/pdf-reviewer/start.bat
    ├── LISEZ-MOI.txt           # quick-start FR for the colleague
    ├── PACKAGE_README.md       # detailed reference
    ├── apps/pdf-reviewer/      # full app (backend + frontend sources, no node_modules / .venv / data)
    │   └── frontend/dist/      # built React UI (only if pnpm + node are available distributor-side)
    ├── design-tokens/          # required by the preview HTML for CSS variables
    └── python-embed/           # bundled Python 3.11 (Windows embeddable + bootstrapped pip)

Excluded everywhere:
    - `.venv/`, `__pycache__/`, `*.pyc`     — runtime venv & bytecode (recreated at first launch)
    - `data/`                               — local SQLite + uploaded PDFs (user state)
    - `node_modules/`, `.cache/`            — package manager + script caches
    - `.git/`, `.claude/`, IDE / cache dirs

Usage:
    python scripts/package_pdf_reviewer.py
    python scripts/package_pdf_reviewer.py --version 0.2.0 --out dist
    python scripts/package_pdf_reviewer.py --no-embed-python  # external Python required
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
    "ftm_backend.egg-info",
    "pdf_reviewer_backend.egg-info",
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
chcp 65001 >nul
REM One-click entry point — delegates to apps/pdf-reviewer/start.bat
cd /d "%~dp0\\apps\\pdf-reviewer"
call start.bat
"""


# ---- Frontend build -------------------------------------------------------

def _build_frontend(frontend_dir: Path) -> bool:
    """Run `pnpm install && pnpm build` so `frontend/dist/` ends up in the zip.

    Returns True if the build succeeded and dist/ exists. Returns False on any
    failure (pnpm/node absent, build error) — the recipient then falls back to
    the backend's preview HTML mode.
    """
    if shutil.which("pnpm") is None or shutil.which("node") is None:
        print("[frontend] pnpm/node not found — skipping build")
        print("           (recipient sees preview HTML; install pnpm+node to bundle React UI)")
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
    """Download (or reuse) the Windows embeddable Python build, extract it
    into a fresh dir, patch `_pth` to enable site-packages, bootstrap pip."""
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
        print(f"[cache] reusing get-pip.py")

    work = Path(tempfile.mkdtemp(prefix="pdf-reviewer-embed-"))
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

    print("[embed] bootstrapping pip…")
    subprocess.run(
        [str(work / "python.exe"), str(get_pip), "--no-warn-script-location"],
        check=True,
        cwd=work,
    )
    print("[embed] pip OK")
    return work


_LISEZ_MOI = """\
PDF Reviewer — Démarrage rapide
================================

1. Décompresser ce ZIP dans le dossier de votre choix.
2. Double-cliquer sur start.bat à la racine.

Au premier lancement (1 à 3 minutes) :
  - Python est détecté ou auto-installé.
  - Les dépendances Python sont installées.
  - Le navigateur s'ouvre sur http://127.0.0.1:8001/

Lancements suivants : ~5 secondes.

Pour arrêter : Ctrl+C dans la fenêtre noire.

Documentation détaillée : voir PACKAGE_README.md.
"""


_PACKAGE_README = """\
# PDF Reviewer — Package partageable

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
   (ex. `Documents/pdf-reviewer/`).
2. **Double-clique sur `start.bat`** à la racine du dossier décompressé.
3. Au **premier lancement** (1 à 3 minutes) :
   - Création d'un environnement Python virtuel local (`apps/pdf-reviewer/backend/.venv/`).
   - Installation des dépendances Python (FastAPI, PyMuPDF, structlog, etc.).
   - Initialisation de la base SQLite locale.
4. Le navigateur s'ouvre automatiquement sur `http://127.0.0.1:8001/`.

Aux lancements suivants : **~5 secondes**.

Pour arrêter le serveur : ferme la fenêtre `cmd` ou fais `Ctrl+C` dedans.

## Configurer Mistral (optionnel)

1. Onglet **Paramètres** → **Configuration Mistral**.
2. Colle ta clé API, **Sauvegarder**, puis **Tester la connexion**.
3. La clé est stockée localement (SQLite, dans `apps/pdf-reviewer/backend/data/`).

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
`apps/pdf-reviewer/backend/data/`.

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
        description="Package pdf-reviewer into a standalone zip.",
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
             "are absent). Use --no-build-frontend to ship preview-only.",
    )
    args = parser.parse_args(argv)

    repo = Path(__file__).resolve().parent.parent
    out_dir: Path = (repo / args.out).resolve() if not args.out.is_absolute() else args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.date.today().strftime("%Y%m%d")
    pkg_name = f"pdf-reviewer-v{args.version}-{stamp}"
    zip_path = out_dir / f"{pkg_name}.zip"
    if zip_path.exists():
        zip_path.unlink()

    print(f"[package] building {zip_path.relative_to(repo)}")

    if args.build_frontend:
        _build_frontend(repo / "apps" / "pdf-reviewer" / "frontend")

    sources = ["apps/pdf-reviewer", "design-tokens"]
    files = _walk_sources(repo, sources)

    embed_dir: Path | None = None
    if args.embed_python:
        try:
            embed_dir = _prepare_embedded_python(out_dir / ".cache")
        except Exception as exc:  # noqa: BLE001
            print(f"[error] embedded Python preparation failed: {exc}", file=sys.stderr)
            print("[hint] re-run with --no-embed-python to skip the bundled Python", file=sys.stderr)
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
