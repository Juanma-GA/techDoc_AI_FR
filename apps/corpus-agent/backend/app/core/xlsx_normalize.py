"""Normalisation d'un .xlsx illisible par openpyxl, via LibreOffice headless.

Certains classeurs — « Strict Open XML Spreadsheet » enregistré par Excel, ou
exports d'outils tiers — s'ouvrent sans erreur mais openpyxl n'y voit AUCUN
onglet (le format strict/non standard n'est pas géré). On les re-sauvegarde
alors en .xlsx « transitional » standard via LibreOffice (`soffice --convert-to
xlsx`), qu'openpyxl relit sans problème.

Best-effort : `normalize_xlsx_bytes` renvoie None si LibreOffice est absent ou si
la conversion échoue — l'appelant retombe alors sur son comportement d'origine.
Même approche que word-reviewer (`core/doc_convert.py`) pour les .doc, mais
corpus-agent reste indépendant (module propre, aucune dépendance runtime croisée).
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger("corpus_agent.xlsx_normalize")

_SOFFICE_CANDIDATES = [
    "soffice",
    "libreoffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]

# LibreOffice portable (sans install admin) — jokers NON récursifs uniquement.
_SOFFICE_PORTABLE_GLOBS = [
    os.path.expandvars(r"%LOCALAPPDATA%\LibreOffice*\program\soffice.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\LibreOfficePortable\App\libreoffice\program\soffice.exe"),
    os.path.expandvars(r"%USERPROFILE%\LibreOffice*\program\soffice.exe"),
    os.path.expandvars(r"%USERPROFILE%\Desktop\LibreOfficePortable\App\libreoffice\program\soffice.exe"),
    os.path.expandvars(r"%USERPROFILE%\Downloads\LibreOfficePortable\App\libreoffice\program\soffice.exe"),
]


def find_soffice() -> str | None:
    """Localise `soffice.exe`. Override explicite via `CORPUS_SOFFICE_PATH` ou
    `WR_SOFFICE_PATH` (déjà posé par l'utilisateur pour word-reviewer)."""
    for var in ("CORPUS_SOFFICE_PATH", "WR_SOFFICE_PATH"):
        env = os.environ.get(var, "").strip().strip('"')
        if env:
            p = Path(env)
            if p.is_dir():
                p = p / "soffice.exe"
            if p.exists():
                return str(p)
    for cand in _SOFFICE_CANDIDATES:
        if cand.lower().endswith(".exe"):
            if Path(cand).exists():
                return cand
        else:
            found = shutil.which(cand)
            if found:
                return found
    for pattern in _SOFFICE_PORTABLE_GLOBS:
        for hit in glob.glob(pattern):
            if Path(hit).exists():
                return hit
    return None


# Profil LibreOffice dédié (persistant) : isolé d'un LibreOffice éventuellement
# ouvert par l'utilisateur (sinon verrou de profil), réutilisé d'une conversion à
# l'autre (1er lancement ~30 s pour créer le profil, suivants ~5 s).
_LO_PROFILE = Path(tempfile.gettempdir()) / "corpus_lo_profile"


def normalize_xlsx_bytes(data: bytes) -> bytes | None:
    """Re-sauve `data` en .xlsx standard via LibreOffice. Renvoie les octets
    normalisés, ou None si LibreOffice est absent ou si la conversion échoue."""
    soffice = find_soffice()
    if not soffice:
        log.info("LibreOffice introuvable : normalisation xlsx impossible.")
        return None
    tmp = Path(tempfile.mkdtemp(prefix="corpus_xlsx_"))
    src = tmp / "input.xlsx"
    src.write_bytes(data)
    outdir = tmp / "out"
    outdir.mkdir()
    try:
        subprocess.run(
            [
                soffice,
                f"-env:UserInstallation={_LO_PROFILE.as_uri()}",
                "--headless",
                "--norestore",
                "--convert-to",
                "xlsx",
                "--outdir",
                str(outdir),
                str(src),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
        out = outdir / "input.xlsx"
        return out.read_bytes() if out.exists() else None
    except Exception as exc:  # noqa: BLE001
        stderr = getattr(exc, "stderr", b"") or b""
        log.warning(
            "normalisation LibreOffice echouee: %s | stderr=%s",
            exc, stderr.decode("utf-8", "replace")[:300],
        )
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
