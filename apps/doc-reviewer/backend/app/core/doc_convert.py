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
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import structlog

from app.core.errors import AppError

log = structlog.get_logger(__name__)

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
        log.warning("dr_soffice_path_not_found")
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

# LibreOffice refuse une 2e instance sur le meme profil ("verrou de profil") :
# deux conversions concurrentes (ex. import d'un .doc pendant qu'un export
# .docx -> .doc tourne deja) se marchaient dessus et l'une des deux echouait
# avec DOC_CONVERT_UNAVAILABLE alors que LibreOffice est bien installe. On
# serialise donc tout appel soffice avec ce verrou process-local.
_SOFFICE_LOCK = threading.Lock()


def _convert_libreoffice(soffice: str, src: Path, outdir: Path) -> Path | None:
    """Convertit `src` (.doc/.docx) vers PDF via LibreOffice headless."""
    try:
        with _SOFFICE_LOCK:
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
        log.info("libreoffice_convert_ok", target_format="pdf")
    except Exception as exc:  # noqa: BLE001
        log.warning("libreoffice_convert_failed", target_format="pdf", error=type(exc).__name__)
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
        log.warning("word_export_pdf_failed", error=type(exc).__name__)
        return None, type(exc).__name__
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
    log.warning("convert_to_pdf_unavailable")
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


def _convert_libreoffice_format(src: Path, outdir: Path, target_format: str) -> Path | None:
    """Convertit `src` vers `target_format` (ex. "docx", "doc") via LibreOffice
    headless. Generalise `_convert_libreoffice` (fige sur "pdf")."""
    soffice = _find_soffice()
    if not soffice:
        return None
    try:
        with _SOFFICE_LOCK:
            result = subprocess.run(
                [
                    soffice,
                    f"-env:UserInstallation={_LO_PROFILE.as_uri()}",
                    "--headless",
                    "--norestore",
                    "--convert-to",
                    target_format,
                    "--outdir",
                    str(outdir),
                    str(src),
                ],
                check=True,
                capture_output=True,
                timeout=180,
            )
        log.info("libreoffice_convert_ok", target_format=target_format)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "libreoffice_convert_failed",
            target_format=target_format,
            error=type(exc).__name__,
        )
        return None
    out = outdir / (src.stem + f".{target_format}")
    return out if out.exists() else None


def office_to_docx_bytes(data: bytes, suffix: str) -> bytes:
    """Convertit des octets `.doc` (legacy) en `.docx` (OOXML) via LibreOffice,
    pour que la revue **Word native** (pipeline docx) puisse s'appliquer a un
    `.doc` sans passer par le pipeline PDF. Seul LibreOffice est supporte ici
    (Word COM n'exporte pas de .docx fiable hors politique de securite Office).
    """
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    tmp = Path(tempfile.mkdtemp(prefix="dr_doc2docx_"))
    src = tmp / f"input{suffix}"
    src.write_bytes(data)
    try:
        produced = _convert_libreoffice_format(src, tmp, "docx")
        if produced is None or not produced.exists():
            raise AppError(
                "DOC_CONVERT_UNAVAILABLE",
                "Conversion .doc -> .docx impossible sur ce poste : LibreOffice "
                "n'a pas produit de fichier (absent, ou conversion concurrente "
                "en echec). Verifiez DR_SOFFICE_PATH, ou reessayez.",
                status_code=400,
            )
        return produced.read_bytes()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def docx_to_doc_bytes(data: bytes) -> bytes:
    """Convertit des octets `.docx` (revise nativement) vers `.doc` (legacy),
    pour rendre a l'export le format d'origine de l'utilisateur sans etape de
    conversion manuelle de sa part."""
    tmp = Path(tempfile.mkdtemp(prefix="dr_docx2doc_"))
    src = tmp / "input.docx"
    src.write_bytes(data)
    try:
        produced = _convert_libreoffice_format(src, tmp, "doc")
        if produced is None or not produced.exists():
            raise AppError(
                "DOC_CONVERT_UNAVAILABLE",
                "Conversion .docx -> .doc impossible sur ce poste : LibreOffice "
                "n'a pas produit de fichier (absent, ou conversion concurrente "
                "en echec). Verifiez DR_SOFFICE_PATH, ou reessayez.",
                status_code=400,
            )
        return produced.read_bytes()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pdf_to_docx_bytes(data: bytes) -> bytes:
    """Convertit un PDF en DOCX via LibreOffice.

    Cette conversion est volontairement une sortie de compatibilite: elle ne
    preserve pas fidelement la mise en page PDF et doit etre signalee comme
    degradee dans l'interface.
    """
    tmp = Path(tempfile.mkdtemp(prefix="dr_pdf2docx_"))
    src = tmp / "input.pdf"
    src.write_bytes(data)
    try:
        produced = _convert_libreoffice_format(src, tmp, "docx")
        if produced is None or not produced.exists():
            raise AppError(
                "DOC_CONVERT_UNAVAILABLE",
                "Conversion PDF -> DOCX impossible sur ce poste : LibreOffice "
                "n'a pas produit de fichier. Verifiez DR_SOFFICE_PATH, ou "
                "conservez l'export PDF natif.",
                status_code=409,
            )
        return produced.read_bytes()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pdf_to_doc_bytes(data: bytes) -> bytes:
    """Convertit un PDF en DOC via la chaine degradee PDF -> DOCX -> DOC."""
    return docx_to_doc_bytes(pdf_to_docx_bytes(data))

