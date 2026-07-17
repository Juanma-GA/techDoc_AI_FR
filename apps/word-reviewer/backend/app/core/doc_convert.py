"""Conversion .doc (binaire legacy) -> .docx.

python-docx ne lit que le .docx. Pour accepter les .doc, on convertit a l'upload
via, dans l'ordre : LibreOffice headless (`soffice --convert-to docx`) puis, a
defaut, MS Word par automation COM (pywin32, si Word est installe). Si aucun
convertisseur n'est disponible, on leve une erreur claire invitant a installer
LibreOffice ou a enregistrer en .docx.
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

log = logging.getLogger("word_reviewer.doc_convert")

# Emplacements standards d'un LibreOffice installe.
_SOFFICE_CANDIDATES = [
    "soffice",
    "libreoffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]

# Emplacements typiques d'un LibreOffice **portable** (sans install admin), a la
# maniere du Node portable. Jokers NON recursifs uniquement (un `**` sur le home
# scannerait tout le profil -> lent). Pour un emplacement exotique : WR_SOFFICE_PATH.
_SOFFICE_PORTABLE_GLOBS = [
    os.path.expandvars(r"%LOCALAPPDATA%\LibreOffice*\program\soffice.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\LibreOfficePortable\App\libreoffice\program\soffice.exe"),
    os.path.expandvars(r"%USERPROFILE%\LibreOffice*\program\soffice.exe"),
    os.path.expandvars(r"%USERPROFILE%\Desktop\LibreOfficePortable\App\libreoffice\program\soffice.exe"),
    os.path.expandvars(r"%USERPROFILE%\Downloads\LibreOfficePortable\App\libreoffice\program\soffice.exe"),
]


def _find_soffice() -> str | None:
    # 1) Override explicite (chemin direct vers soffice.exe ou son dossier).
    env = os.environ.get("WR_SOFFICE_PATH", "").strip().strip('"')
    if env:
        p = Path(env)
        if p.is_dir():
            p = p / "soffice.exe"
        if p.exists():
            return str(p)
        log.warning("WR_SOFFICE_PATH defini mais introuvable: %s", env)
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


# Profil LibreOffice DEDIE (persistant) : isole d'un eventuel LibreOffice ouvert
# par l'utilisateur (sinon verrou de profil -> conversion en echec), et reutilise
# d'une conversion a l'autre (le 1er lancement cree le profil ~30 s, les suivants
# ~5 s). URI file:// exige par -env:UserInstallation.
_LO_PROFILE = Path(tempfile.gettempdir()) / "wr_lo_profile"


def _convert_libreoffice(soffice: str, src: Path, outdir: Path, fmt: str = "docx") -> Path | None:
    """Convertit `src` vers `fmt` (docx, pdf, ...) via LibreOffice headless."""
    try:
        result = subprocess.run(
            [
                soffice,
                f"-env:UserInstallation={_LO_PROFILE.as_uri()}",
                "--headless",
                "--norestore",
                "--convert-to",
                fmt,
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
    out = outdir / (src.stem + f".{fmt}")
    return out if out.exists() else None


def _word_export_pdf(src: Path, out: Path) -> tuple[Path | None, str | None]:
    """Export PDF via Word COM (ExportAsFixedFormat). Rendu Word EXACT, et l'export
    PDF n'est PAS bloque par la politique Office (contrairement au SaveAs .docx).
    Word ouvre aussi bien un .doc qu'un .docx.
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
    return (out, None) if out.exists() else (None, "Word n'a produit aucun PDF.")


def convert_to_pdf(src: Path, outdir: Path) -> Path | None:
    """Produit un PDF fidele de `src` (.doc ou .docx). Priorite a **Word** (rendu
    exact, disponible ici), repli **LibreOffice**. None si aucun convertisseur.
    """
    out = outdir / (src.stem + ".pdf")
    produced, _ = _word_export_pdf(src, out)
    if produced is not None and produced.exists():
        return produced
    soffice = _find_soffice()
    if soffice:
        return _convert_libreoffice(soffice, src, outdir, fmt="pdf")
    log.warning("convert_to_pdf: ni Word ni LibreOffice disponibles.")
    return None


def docx_to_pdf(src: Path, outdir: Path) -> Path | None:
    """Compat : PDF fidele de `src` (delegue a convert_to_pdf : Word puis LibreOffice)."""
    return convert_to_pdf(src, outdir)


# Code COM renvoye par Word quand l'enregistrement OOXML (.docx) est bloque par
# la configuration Office (Trust Center / GPO "File Block") : "La commande a
# echoue" (0x800A1066). Word reste utilisable pour ouvrir/sauver en .doc/RTF/PDF,
# mais pas pour produire le .docx dont l'analyseur a besoin.
_WORD_SAVE_BLOCKED = -2146824090


def _convert_word_com(src: Path, out: Path) -> tuple[Path | None, str | None]:
    """(.docx produit ou None, raison d'echec lisible ou None)."""
    try:
        import pythoncom  # type: ignore[import-untyped]
        import win32com.client  # type: ignore[import-untyped]
    except ImportError:
        return None, "Word indisponible (pywin32 absent)."
    word = None
    try:
        pythoncom.CoInitialize()
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0  # wdAlertsNone : pas de dialogue bloquant
        doc = word.Documents.Open(
            FileName=str(src),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
        )
        try:
            doc.SaveAs(str(out), FileFormat=16)  # 16 = wdFormatDocumentDefault (.docx)
        finally:
            doc.Close(False)
    except Exception as exc:  # noqa: BLE001
        log.warning("conversion Word COM echouee: %s", exc)
        blocked = str(_WORD_SAVE_BLOCKED) in str(exc)
        reason = (
            "Word ne peut pas enregistrer en .docx sur ce poste : le format Office "
            "moderne (.docx) est bloque par la configuration Office (Trust Center / "
            "strategie d'entreprise)."
            if blocked
            else f"Echec de la conversion Word ({exc})."
        )
        return None, reason
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:  # noqa: BLE001
                pass
    return (out, None) if out.exists() else (None, "Word n'a produit aucun fichier.")


def doc_to_docx_bytes(data: bytes) -> bytes:
    """Convertit des octets .doc en octets .docx. Leve AppError si indisponible.

    Le fichier de travail vit dans `%TEMP%` (dossier local hors OneDrive) : la
    SaveAs COM de Word echoue vers un dossier synchronise OneDrive, alors qu'elle
    fonctionne dans le temp local.
    """
    tmp = Path(tempfile.mkdtemp(prefix="wr_doc_"))
    src = tmp / "input.doc"
    src.write_bytes(data)
    out = tmp / "input.docx"

    try:
        soffice = _find_soffice()
        result = _convert_libreoffice(soffice, src, tmp) if soffice else None
        word_reason: str | None = None
        if result is None:
            result, word_reason = _convert_word_com(src, out)
        if result is None or not result.exists():
            # Message le plus precis possible selon ce qui a echoue.
            cause = word_reason or "Aucun convertisseur disponible (ni LibreOffice, ni Word)."
            raise AppError(
                "DOC_CONVERT_UNAVAILABLE",
                f"Conversion .doc -> .docx impossible sur ce poste. {cause} "
                "Solutions : ouvrir le fichier dans Word puis l'enregistrer en .docx "
                "(Fichier > Enregistrer sous), ou installer LibreOffice (meme portable, "
                "sans admin) et definir la variable d'environnement WR_SOFFICE_PATH vers "
                "soffice.exe.",
                400,
            )
        return result.read_bytes()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
