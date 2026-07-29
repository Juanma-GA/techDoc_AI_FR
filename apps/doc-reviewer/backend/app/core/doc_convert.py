"""Conversion .doc / .docx -> PDF **fidele**.

Doc Reviewer revise un **PDF** pour tout format d'entree. Pour une qualite de
revue **homogene d'un poste a l'autre**, on privilegie **LibreOffice**
(`--convert-to pdf`, headless) : le rendu est reproductible et independant du
Word installe localement, et LibreOffice tourne en portable sans droits admin.
Repli **Word COM** (`ExportAsFixedFormat`, rendu Word exact mais dependant de la
version/config Word du poste, donc moins reproductible) quand LibreOffice est
absent. On ne produit jamais de `.docx` ici : la voie `.doc -> .docx` (lossy)
est justement ce que l'app evite.

Le convertisseur reellement utilise est **remonte a l'appelant** (`libreoffice`
ou `word`) et trace sur le document, car les checks geometriques (layout)
dependent du moteur de rendu.

Override du chemin soffice : variable d'environnement `DR_SOFFICE_PATH`.
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.errors import AppError

log = logging.getLogger("doc_reviewer.doc_convert")

# Emplacements standards d'un LibreOffice installe.
_SOFFICE_CANDIDATES = [
    "soffice",
    "libreoffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]

# Emplacements typiques d'un LibreOffice **portable** (sans install admin). Jokers
# NON recursifs uniquement. Pour un emplacement exotique : DR_SOFFICE_PATH.
_SOFFICE_PORTABLE_GLOBS = [
    os.path.expandvars(r"%LOCALAPPDATA%\LibreOffice*\program\soffice.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\LibreOfficePortable\App\libreoffice\program\soffice.exe"),
    os.path.expandvars(r"%USERPROFILE%\LibreOffice*\program\soffice.exe"),
    os.path.expandvars(r"%USERPROFILE%\Desktop\LibreOfficePortable\App\libreoffice\program\soffice.exe"),
    os.path.expandvars(r"%USERPROFILE%\Downloads\LibreOfficePortable\App\libreoffice\program\soffice.exe"),
]


def _find_soffice() -> str | None:
    # 1) Override explicite (chemin direct vers soffice.exe ou son dossier).
    env = os.environ.get("DR_SOFFICE_PATH", "").strip().strip('"')
    if env:
        p = Path(env)
        if p.is_dir():
            p = p / "soffice.exe"
        if p.exists():
            return str(p)
        log.warning("DR_SOFFICE_PATH defini mais introuvable: %s", env)
    # 2) Emplacements standards (PATH + Program Files).
    for cand in _SOFFICE_CANDIDATES:
        if cand.lower().endswith(".exe"):
            if Path(cand).exists():
                return cand
        else:
            found = shutil.which(cand)
            if found:
                return found
    # 3) LibreOffice portable (recherche par jokers, best-effort).
    for pattern in _SOFFICE_PORTABLE_GLOBS:
        for hit in glob.glob(pattern):
            if Path(hit).exists():
                return hit
    return None


# Profil LibreOffice DEDIE (persistant) : isole d'un LibreOffice ouvert par
# l'utilisateur (sinon verrou de profil -> conversion en echec), et reutilise
# d'une conversion a l'autre. URI file:// exige par -env:UserInstallation.
_LO_PROFILE = Path(tempfile.gettempdir()) / "dr_lo_profile"


def _convert_libreoffice(soffice: str, src: Path, outdir: Path) -> Path | None:
    """Convertit `src` (.doc/.docx) vers PDF via LibreOffice headless."""
    try:
        result = subprocess.run(
            [
                soffice,
                f"-env:UserInstallation={_LO_PROFILE.as_uri()}",
                "--headless",
                "--norestore",
                "--convert-to",
                "pdf",
                "--outdir",
                str(outdir),
                str(src),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
        log.info("LibreOffice convert ok: %s", (result.stdout or b"").decode("utf-8", "replace").strip()[:200])
    except Exception as exc:  # noqa: BLE001
        stderr = getattr(exc, "stderr", b"") or b""
        log.warning("conversion LibreOffice echouee: %s | stderr=%s", exc, stderr.decode("utf-8", "replace")[:300])
        return None
    out = outdir / (src.stem + ".pdf")
    return out if out.exists() else None


def _word_export_pdf(src: Path, out: Path) -> tuple[Path | None, str | None]:
    """Export PDF via Word COM (ExportAsFixedFormat). Rendu Word EXACT, et l'export
    PDF n'est PAS bloque par la politique Office (contrairement au SaveAs .docx).
    Word ouvre aussi bien un .doc qu'un .docx. Tourne dans un thread COM dedie
    (CoInitialize) pour ne pas polluer la boucle async d'uvicorn.
    """
    try:
        import pythoncom  # type: ignore[import-untyped]
        import win32com.client  # type: ignore[import-untyped]
    except ImportError:
        return None, "pywin32 absent"
    word = None
    try:
        pythoncom.CoInitialize()
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(
            FileName=str(src), ConfirmConversions=False, ReadOnly=True, AddToRecentFiles=False
        )
        try:
            doc.ExportAsFixedFormat(OutputFileName=str(out), ExportFormat=17)  # 17 = wdExportFormatPDF
        finally:
            doc.Close(False)
    except Exception as exc:  # noqa: BLE001
        log.warning("export PDF Word echoue: %s", exc)
        return None, str(exc)
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:  # noqa: BLE001
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:  # noqa: BLE001
            pass
    return (out, None) if out.exists() else (None, "Word n'a produit aucun PDF.")


def convert_to_pdf(src: Path, outdir: Path) -> tuple[Path | None, str | None]:
    """Produit un PDF fidele de `src` (.doc ou .docx). Priorite **LibreOffice**
    (rendu reproductible, portable), repli **Word COM** (rendu Word exact mais
    dependant du poste). Retourne `(pdf, engine)` avec `engine` in
    {"libreoffice", "word"}, ou `(None, None)` si aucun convertisseur.
    """
    soffice = _find_soffice()
    if soffice:
        produced = _convert_libreoffice(soffice, src, outdir)
        if produced is not None and produced.exists():
            return produced, "libreoffice"
    out = outdir / (src.stem + ".pdf")
    produced, _ = _word_export_pdf(src, out)
    if produced is not None and produced.exists():
        return produced, "word"
    log.warning("convert_to_pdf: ni LibreOffice ni Word disponibles.")
    return None, None


def doc_to_pdf_bytes(data: bytes, suffix: str) -> tuple[bytes, str]:
    """Convertit des octets .doc/.docx en octets **PDF fidele**. Retourne
    `(pdf_bytes, engine)` (engine in {"libreoffice", "word"}). Leve AppError si
    indisponible.

    Le fichier de travail vit dans `%TEMP%` (dossier local hors OneDrive) :
    l'automation Word echoue vers un dossier synchronise OneDrive, alors qu'elle
    fonctionne dans le temp local.
    """
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    tmp = Path(tempfile.mkdtemp(prefix="dr_doc_"))
    src = tmp / f"input{suffix}"
    src.write_bytes(data)
    try:
        produced, engine = convert_to_pdf(src, tmp)
        if produced is None or not produced.exists():
            raise AppError(
                "DOC_CONVERT_UNAVAILABLE",
                "Conversion Word -> PDF impossible sur ce poste : ni LibreOffice "
                "ni Word (automation COM) ne sont disponibles. Solutions : installer "
                "LibreOffice (meme portable, sans admin) et definir la variable "
                "d'environnement DR_SOFFICE_PATH vers soffice.exe, ou ouvrir le "
                "fichier dans Word et l'exporter en PDF.",
                status_code=400,
            )
        return produced.read_bytes(), engine or "unknown"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
