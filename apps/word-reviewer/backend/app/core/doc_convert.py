"""Conversion .doc (binaire legacy) -> .docx.

python-docx ne lit que le .docx. Pour accepter les .doc, on convertit a l'upload
via, dans l'ordre : LibreOffice headless (`soffice --convert-to docx`) puis, a
defaut, MS Word par automation COM (pywin32, si Word est installe). Si aucun
convertisseur n'est disponible, on leve une erreur claire invitant a installer
LibreOffice ou a enregistrer en .docx.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.errors import AppError

log = logging.getLogger("word_reviewer.doc_convert")

_SOFFICE_CANDIDATES = [
    "soffice",
    "libreoffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]


def _find_soffice() -> str | None:
    for cand in _SOFFICE_CANDIDATES:
        if cand.lower().endswith(".exe"):
            if Path(cand).exists():
                return cand
        else:
            found = shutil.which(cand)
            if found:
                return found
    return None


def _convert_libreoffice(soffice: str, src: Path, outdir: Path) -> Path | None:
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "docx", "--outdir", str(outdir), str(src)],
            check=True,
            capture_output=True,
            timeout=180,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("conversion LibreOffice echouee: %s", exc)
        return None
    out = outdir / (src.stem + ".docx")
    return out if out.exists() else None


def _convert_word_com(src: Path, out: Path) -> Path | None:
    try:
        import pythoncom  # type: ignore[import-untyped]
        import win32com.client  # type: ignore[import-untyped]
    except ImportError:
        return None
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
        doc.SaveAs(str(out), FileFormat=16)  # 16 = wdFormatXMLDocument (.docx)
        doc.Close(False)
    except Exception as exc:  # noqa: BLE001
        log.warning("conversion Word COM echouee: %s", exc)
        return None
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:  # noqa: BLE001
                pass
    return out if out.exists() else None


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
        if result is None:
            result = _convert_word_com(src, out)
        if result is None or not result.exists():
            raise AppError(
                "DOC_CONVERT_UNAVAILABLE",
                "Conversion .doc indisponible sur ce poste. Installez LibreOffice "
                "ou enregistrez le fichier en .docx.",
                400,
            )
        return result.read_bytes()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
