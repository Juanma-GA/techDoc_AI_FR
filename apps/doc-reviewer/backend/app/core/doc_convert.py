"""Conversions bureautiques : .doc / .docx / PDF.

Moteur principal : **Microsoft Word** (automation COM), present sur tous les
postes ATEXIS (Microsoft 365). Il couvre toutes les conversions de l'app :

- .doc / .docx -> PDF fidele (`ExportAsFixedFormat`) ;
- .doc -> .docx (pipeline Word natif d'un `.doc`) ;
- .docx -> .doc (export au format d'origine) ;
- PDF -> .docx / .doc (PDF Reflow de Word, sortie de compatibilite degradee).

**Etiquette de confidentialite obligatoire (Microsoft Purview).** Sur un poste
ou l'etiquetage est obligatoire, Word refuse tout enregistrement `.docx` d'un
document sans etiquette (« Command failed ») ; `.doc` et PDF ne portent pas
d'etiquette et ne sont pas concernes. Avant chaque enregistrement `.docx`, on
conserve l'etiquette deja portee par le document, sinon on applique celle
configuree par l'IT (`WORD_SENSITIVITY_LABEL_ID`). On reste ainsi DANS la
politique : aucune sauvegarde ne la contourne.

**Garde-fou.** Une boite de dialogue invisible peut bloquer Word indefiniment.
Chaque conversion Word tourne sous un chien de garde : passe le delai
`WORD_CONVERT_TIMEOUT_SECONDS`, le processus WINWORD de CETTE conversion (et
lui seul) est arrete et la conversion echoue proprement.

**LibreOffice** reste un moteur optionnel (`OFFICE_CONVERTER`) : repli si Word
est absent ou echoue (`auto`), ou moteur unique (`libreoffice`). Chemin
soffice : variable d'environnement `DR_SOFFICE_PATH`.

Le moteur reellement utilise pour un PDF (`word` ou `libreoffice`) est remonte
a l'appelant et trace sur le document, car les checks geometriques (layout)
dependent du moteur de rendu.
"""

from __future__ import annotations

import glob
import io
import logging
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import settings
from app.core.errors import AppError

log = logging.getLogger("doc_reviewer.doc_convert")

# ---------------------------------------------------------------------------
# LibreOffice (moteur optionnel)
# ---------------------------------------------------------------------------

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
    # 1) Override explicite (chemin direct vers soffice.exe ou son dossier),
    #    depuis backend\.env ou l'environnement.
    env = (settings.dr_soffice_path or os.environ.get("DR_SOFFICE_PATH", "")).strip().strip('"')
    if env:
        p = Path(env)
        if p.is_dir():
            p = p / "soffice.exe"
        if p.exists():
            return str(p)
        log.warning("DR_SOFFICE_PATH defini mais introuvable")
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
# deux conversions concurrentes se marchaient dessus. On serialise donc tout
# appel soffice avec ce verrou process-local.
_SOFFICE_LOCK = threading.Lock()


def _libreoffice_command(soffice: str, src: Path, outdir: Path, target_format: str) -> list[str]:
    cmd = [
        soffice,
        f"-env:UserInstallation={_LO_PROFILE.as_uri()}",
        "--headless",
        "--norestore",
    ]
    # Un PDF s'ouvre par defaut dans Draw, qui n'a aucun filtre d'export
    # .docx/.doc ("no export filter") : on force l'import Writer.
    if src.suffix.lower() == ".pdf":
        cmd.append("--infilter=writer_pdf_import")
    return [*cmd, "--convert-to", target_format, "--outdir", str(outdir), str(src)]


def _convert_libreoffice_format(src: Path, outdir: Path, target_format: str) -> Path | None:
    """Convertit `src` vers `target_format` ("pdf", "docx", "doc") via LibreOffice headless."""
    soffice = _find_soffice()
    if not soffice:
        return None
    try:
        with _SOFFICE_LOCK:
            result = subprocess.run(
                _libreoffice_command(soffice, src, outdir, target_format),
                check=True,
                capture_output=True,
                timeout=180,
            )
        log.info(
            "LibreOffice convert (%s) ok: %s",
            target_format,
            (result.stdout or b"").decode("utf-8", "replace").strip()[:200],
        )
    except Exception as exc:  # noqa: BLE001
        stderr = getattr(exc, "stderr", b"") or b""
        stderr_text = stderr.decode("utf-8", "replace") if isinstance(stderr, bytes) else str(stderr)
        log.warning(
            "conversion LibreOffice echouee: target_format=%s error=%s stderr=%s",
            target_format,
            type(exc).__name__,
            stderr_text.strip()[:200],
        )
        return None
    out = outdir / (src.stem + f".{target_format}")
    return out if out.exists() else None


# ---------------------------------------------------------------------------
# Microsoft Word (moteur principal)
# ---------------------------------------------------------------------------

# msoAutomationSecurityForceDisable : aucune macro (VBA, AutoOpen,
# Document_Open, modele attache distant .dotm) ne s'execute a l'ouverture.
# Le defaut d'une instance Word pilotee par COM est msoAutomationSecurityLow
# (= macros ACTIVEES) : un .doc/.docx non fiable ouvert ici executait son code
# avec les droits de l'utilisateur.
_MSO_AUTOMATION_SECURITY_FORCE_DISABLE = 3
# Mot de passe factice : un document protege echoue immediatement au lieu
# d'ouvrir une boite de dialogue invisible qui bloquerait la conversion.
_WORD_DUMMY_PASSWORD = "doc-reviewer-no-password"

# Formats Word (WdSaveFormat / WdExportFormat).
_WD_FORMAT_DOC = 0          # wdFormatDocument (Word 97-2003)
_WD_FORMAT_DOCX = 16        # wdFormatXMLDocument
_WD_EXPORT_PDF = 17         # wdExportFormatPDF
# MsoAssignmentMethod.PRIVILEGED : etiquette posee par l'application (et non
# choisie par l'utilisateur) ; c'est la methode prevue pour l'automation.
_MSO_ASSIGNMENT_PRIVILEGED = 1
_LABEL_JUSTIFICATION = "Doc Reviewer : conversion automatique"

# Conversions Word serialisees : une instance WINWORD par conversion, une a la
# fois (memoire du poste, et un seul processus a surveiller par le garde-fou).
_WORD_LOCK = threading.Lock()


class _WordUnavailableError(RuntimeError):
    """pywin32 ou Word absent : on passe au moteur suivant sans bruit."""


def word_available() -> bool:
    """Word (automation COM) et pywin32 presents sur ce poste."""
    try:
        import winreg

        import win32com.client  # type: ignore[import-untyped]  # noqa: F401
    except ImportError:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID"):
            return True
    except OSError:
        return False


def _harden_word(word: object) -> None:
    """Desactive les macros et les automatismes de Word AVANT toute ouverture.

    Leve si le reglage n'a pas pu etre applique : on prefere echouer la
    conversion plutot qu'ouvrir un document non fiable avec les macros actives.
    """
    word.AutomationSecurity = _MSO_AUTOMATION_SECURITY_FORCE_DISABLE  # type: ignore[attr-defined]
    if word.AutomationSecurity != _MSO_AUTOMATION_SECURITY_FORCE_DISABLE:  # type: ignore[attr-defined]
        raise RuntimeError("Word AutomationSecurity n'a pas pu etre force a 'desactive'.")
    word.Visible = False  # type: ignore[attr-defined]
    word.DisplayAlerts = 0  # type: ignore[attr-defined]  # wdAlertsNone


def _word_pid(caption: str) -> int | None:
    """PID du WINWORD dont la fenetre (cachee) porte `caption`, pour que le
    garde-fou n'arrete QUE l'instance de cette conversion (jamais le Word ouvert
    par l'utilisateur)."""
    try:
        import win32gui  # type: ignore[import-untyped]
        import win32process  # type: ignore[import-untyped]
    except ImportError:
        return None
    found: list[int] = []

    def _match(hwnd: int, _arg: object) -> bool:
        if win32gui.GetClassName(hwnd) == "OpusApp" and win32gui.GetWindowText(hwnd).startswith(caption):
            found.append(win32process.GetWindowThreadProcessId(hwnd)[1])
        return True

    try:
        win32gui.EnumWindows(_match, None)
    except Exception:  # EnumWindows leve si le callback arrete l'enumeration
        pass
    return found[0] if found else None


def _kill_pid(pid: int) -> None:
    subprocess.run(
        [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe"),
         "/PID", str(pid), "/F"],
        capture_output=True,
        check=False,
    )


def _disable_pdf_reflow_prompt(version: str) -> None:
    """Coupe, pour l'utilisateur courant, l'avertissement « Word va convertir
    votre PDF en document modifiable » : affiche par une instance invisible, il
    bloquait la conversion. Reglage d'options Word (HKCU), sans effet de securite."""
    try:
        import winreg
    except ImportError:
        return
    key_path = rf"Software\Microsoft\Office\{version}\Word\Options"
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DisableConvertPdfWarning", 0, winreg.REG_DWORD, 1)
    except OSError as exc:
        log.warning("reglage DisableConvertPdfWarning impossible: %s", exc)


@contextmanager
def _word_session(watch: dict[str, bool]) -> Iterator[object]:
    """Instance Word dediee, durcie et surveillee par le garde-fou
    (`watch["fired"]` passe a True si le garde-fou a du arreter Word)."""
    try:
        import pythoncom  # type: ignore[import-untyped]
        import win32com.client  # type: ignore[import-untyped]
    except ImportError as exc:
        raise _WordUnavailableError("pywin32 absent") from exc
    timeout = settings.word_convert_timeout_seconds
    with _WORD_LOCK:
        pythoncom.CoInitialize()
        word = None
        timer: threading.Timer | None = None
        try:
            try:
                word = win32com.client.DispatchEx("Word.Application")
            except Exception as exc:
                raise _WordUnavailableError(f"Word indisponible: {exc}") from exc
            _harden_word(word)
            caption = f"doc-reviewer-{uuid.uuid4().hex}"
            try:
                word.Caption = caption  # type: ignore[attr-defined]
            except Exception:
                pass
            pid = _word_pid(caption)
            if pid is None:
                log.warning("PID de l'instance Word introuvable : conversion sans garde-fou.")
            else:
                def _expire() -> None:
                    watch["fired"] = True
                    log.error(
                        "conversion Word bloquee depuis %s s : arret de WINWORD (PID %s).", timeout, pid
                    )
                    _kill_pid(pid)

                timer = threading.Timer(timeout, _expire)
                timer.daemon = True
                timer.start()
            yield word
        finally:
            if timer is not None:
                timer.cancel()
            if word is not None:
                try:
                    word.Quit()  # type: ignore[attr-defined]
                except Exception:
                    pass
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def _open_untrusted(word: object, src: Path) -> object:
    """Ouvre un document NON FIABLE : lecture seule, sans reparation ni boite
    de dialogue, macros deja forcees a « desactive » (cf. `_harden_word`)."""
    return word.Documents.Open(  # type: ignore[attr-defined]
        FileName=str(src),
        ConfirmConversions=False,
        ReadOnly=True,
        AddToRecentFiles=False,
        PasswordDocument=_WORD_DUMMY_PASSWORD,
        PasswordTemplate=_WORD_DUMMY_PASSWORD,
        Revert=False,
        OpenAndRepair=False,
        NoEncodingDialog=True,
    )


def _current_label_id(doc: object) -> str:
    try:
        return str(doc.SensitivityLabel.GetLabel().LabelId or "")  # type: ignore[attr-defined]
    except Exception:  # pas d'etiquetage sur ce poste / cette version
        return ""


def _ensure_label(doc: object) -> None:
    """Avant un enregistrement .docx : garde l'etiquette existante, sinon pose
    celle configuree. Sans configuration, on laisse Word decider (poste sans
    etiquetage obligatoire : l'enregistrement passe ; sinon il echoue et le
    message d'erreur indique le reglage a faire)."""
    if _current_label_id(doc):
        return
    label_id = settings.word_sensitivity_label_id.strip()
    if not label_id:
        return
    sensitivity = doc.SensitivityLabel  # type: ignore[attr-defined]
    info = sensitivity.CreateLabelInfo()
    info.LabelId = label_id
    info.AssignmentMethod = _MSO_ASSIGNMENT_PRIVILEGED
    info.Justification = _LABEL_JUSTIFICATION
    sensitivity.SetLabel(info, info)


_WATCHDOG_MARK = "garde-fou"


def _is_retryable(error: str) -> bool:
    """Echec transitoire de Word (appel COM rejete, serveur RPC perdu...) : une
    nouvelle instance a de bonnes chances de reussir. Jamais un refus de la
    politique (etiquette), un durcissement impossible (macros), ni un blocage
    deja arrete par le garde-fou."""
    lowered = error.lower()
    return not (
        "command failed" in lowered
        or error.startswith(_WATCHDOG_MARK)
        or "automationsecurity" in lowered
        or "pywin32 absent" in lowered
        or "word indisponible" in lowered
    )


def _word_convert(src: Path, out: Path, target: str) -> tuple[Path | None, str | None]:
    """Convertit `src` vers `target` ("pdf", "docx", "doc") avec Word.
    Retourne `(fichier, None)` ou `(None, erreur)`. Un echec transitoire est
    retente UNE fois avec une nouvelle instance Word."""
    produced, error = _word_convert_once(src, out, target)
    if produced is None and error and _is_retryable(error):
        log.warning("conversion Word (%s -> %s) : nouvel essai apres : %s", src.suffix, target, error)
        out.unlink(missing_ok=True)
        produced, error = _word_convert_once(src, out, target)
    return produced, error


def _word_convert_once(src: Path, out: Path, target: str) -> tuple[Path | None, str | None]:
    watch: dict[str, bool] = {}
    # Passe a True des que l'export / l'enregistrement a RENDU la main : le
    # fichier de sortie est alors complet. Word plante parfois a la fermeture
    # de certains documents (deconnexion COM pendant Close/Quit) : ce plantage
    # ne doit pas jeter une conversion deja reussie.
    written = False
    try:
        with _word_session(watch) as word:
            if src.suffix.lower() == ".pdf":
                _disable_pdf_reflow_prompt(str(getattr(word, "Version", "16.0")))
            doc = _open_untrusted(word, src)
            try:
                if target == "pdf":
                    doc.ExportAsFixedFormat(OutputFileName=str(out), ExportFormat=_WD_EXPORT_PDF)
                elif target == "docx":
                    _ensure_label(doc)
                    doc.SaveAs2(FileName=str(out), FileFormat=_WD_FORMAT_DOCX)
                elif target == "doc":
                    doc.SaveAs2(FileName=str(out), FileFormat=_WD_FORMAT_DOC)
                else:
                    raise ValueError(f"format cible inconnu: {target}")
                written = True
            finally:
                doc.Close(False)
    except _WordUnavailableError as exc:
        return None, str(exc)
    except Exception as exc:
        if written and not watch.get("fired") and out.exists() and out.stat().st_size > 0:
            log.warning(
                "Word s'est deconnecte a la fermeture (%s -> %s) apres avoir ecrit le fichier : "
                "conversion conservee (%r)", src.suffix, target, exc,
            )
            return out, None
        log.warning("conversion Word (%s -> %s) echouee: %r", src.suffix, target, exc)
        if watch.get("fired"):
            limit = settings.word_convert_timeout_seconds
            return None, f"{_WATCHDOG_MARK} : Word bloque plus de {limit} s, arrete."
        return None, str(exc)
    return (out, None) if out.exists() else (None, f"Word n'a produit aucun fichier {target}.")


def _word_export_pdf(src: Path, out: Path) -> tuple[Path | None, str | None]:
    """Export PDF fidele via Word (ExportAsFixedFormat) d'un .doc ou .docx."""
    return _word_convert(src, out, "pdf")


# ---------------------------------------------------------------------------
# Orchestration des moteurs
# ---------------------------------------------------------------------------


def _engines() -> list[str]:
    choice = settings.office_converter
    if choice == "word":
        return ["word"]
    if choice == "libreoffice":
        return ["libreoffice"]
    return ["word", "libreoffice"]


def can_convert_formats() -> bool:
    """Un moteur capable des conversions .doc/.docx/PDF est present (sert a
    proposer, ou non, les exports convertis dans l'interface)."""
    for engine in _engines():
        if engine == "word" and word_available():
            return True
        if engine == "libreoffice" and _find_soffice():
            return True
    return False


def _label_hint(errors: list[str], target: str) -> str:
    if target == "docx" and any("command failed" in e.lower() for e in errors):
        return (
            " Word a refuse d'enregistrer le .docx : une etiquette de "
            "confidentialite est obligatoire sur ce poste. L'IT doit renseigner "
            "WORD_SENSITIVITY_LABEL_ID dans backend\\.env (cf. guide d'installation)."
        )
    return ""


_OLE2_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")  # Word 97-2003 (.doc)


def _require_genuine_format(data: bytes, suffix: str) -> None:
    """Le contenu doit etre du format annonce par l'extension AVANT d'etre
    confie a Word. Word ouvre n'importe quoi (RTF, HTML, MHT, texte) renomme en
    `.doc` : des formats historiquement porteurs d'exploits (equation editor,
    ms-msdt...) qui n'ont rien a faire dans une revue documentaire."""
    if suffix == ".doc":
        genuine = data.startswith(_OLE2_MAGIC)
    elif suffix == ".docx":
        genuine = data.startswith(b"PK")
        if genuine:
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    genuine = "[Content_Types].xml" in archive.namelist()
            except zipfile.BadZipFile:
                genuine = False
    elif suffix == ".pdf":
        genuine = data[:1024].lstrip().startswith(b"%PDF-")
    else:
        genuine = False
    if not genuine:
        raise AppError(
            "DOC_INVALID",
            f"Le fichier n'est pas un {suffix} valide (contenu d'un autre format). "
            "Ouvrez-le dans Word et enregistrez-le en .docx avant de le soumettre.",
            status_code=400,
        )


def _convert(data: bytes, suffix: str, target: str) -> tuple[bytes | None, str | None, list[str]]:
    """Ecrit `data` dans %TEMP% puis essaie chaque moteur. Retourne
    `(octets, moteur, erreurs)`.

    Le fichier de travail vit dans `%TEMP%` (dossier local hors OneDrive) :
    l'automation Word echoue vers un dossier synchronise OneDrive.
    """
    suffix = (suffix if suffix.startswith(".") else f".{suffix}").lower()
    _require_genuine_format(data, suffix)
    tmp = Path(tempfile.mkdtemp(prefix="dr_conv_"))
    src = tmp / f"input{suffix}"
    src.write_bytes(data)
    errors: list[str] = []
    try:
        for engine in _engines():
            if engine == "word":
                out = tmp / f"word-output.{target}"
                produced, error = _word_convert(src, out, target)
            else:
                lo_dir = tmp / "lo"
                lo_dir.mkdir(exist_ok=True)
                produced = _convert_libreoffice_format(src, lo_dir, target)
                error = None if produced else (
                    "conversion en echec (voir le journal)" if _find_soffice()
                    else "LibreOffice introuvable (installer LibreOffice ou definir DR_SOFFICE_PATH)"
                )
            if produced is not None and produced.exists():
                return produced.read_bytes(), engine, errors
            errors.append(f"{engine}: {error}")
        return None, None, errors
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _unavailable(message: str, errors: list[str], target: str, status_code: int) -> AppError:
    log.warning("%s | %s", message, " ; ".join(errors))
    return AppError(
        "DOC_CONVERT_UNAVAILABLE",
        message + _label_hint(errors, target),
        status_code=status_code,
        detail={"engines": errors},
    )


def doc_to_pdf_bytes(data: bytes, suffix: str) -> tuple[bytes, str]:
    """Convertit des octets .doc/.docx en octets **PDF fidele**. Retourne
    `(pdf_bytes, engine)` (engine in {"word", "libreoffice"})."""
    pdf, engine, errors = _convert(data, suffix, "pdf")
    if pdf is None:
        raise _unavailable(
            "Conversion Word -> PDF impossible sur ce poste : Microsoft Word "
            "(automation COM) n'a pas pu convertir le fichier, et aucun autre "
            "moteur n'est disponible.",
            errors, "pdf", 400,
        )
    return pdf, engine or "unknown"


def office_to_docx_bytes(data: bytes, suffix: str) -> tuple[bytes, str]:
    """Convertit des octets `.doc` (legacy) en `.docx` (OOXML), pour que la revue
    **Word native** (pipeline docx) s'applique a un `.doc`. Retourne
    `(docx_bytes, engine)` (engine in {"word", "libreoffice"})."""
    docx, engine, errors = _convert(data, suffix, "docx")
    if docx is None:
        raise _unavailable(
            "Conversion .doc -> .docx impossible sur ce poste.", errors, "docx", 400
        )
    return docx, engine or "unknown"


def docx_to_doc_bytes(data: bytes) -> bytes:
    """Convertit des octets `.docx` (revise nativement) vers `.doc` (legacy),
    pour rendre a l'export le format d'origine de l'utilisateur."""
    doc, _, errors = _convert(data, ".docx", "doc")
    if doc is None:
        raise _unavailable(
            "Conversion .docx -> .doc impossible sur ce poste.", errors, "doc", 400
        )
    return doc


def pdf_to_docx_bytes(data: bytes) -> bytes:
    """Convertit un PDF en DOCX (PDF Reflow de Word, ou LibreOffice).

    Sortie de compatibilite : la mise en page PDF n'est pas preservee fidelement,
    ce que l'interface signale."""
    docx, _, errors = _convert(data, ".pdf", "docx")
    if docx is None:
        raise _unavailable(
            "Conversion PDF -> DOCX impossible sur ce poste ; conservez l'export PDF natif.",
            errors, "docx", 409,
        )
    return docx


def pdf_to_doc_bytes(data: bytes) -> bytes:
    """Convertit un PDF en DOC (sortie de compatibilite degradee)."""
    doc, _, errors = _convert(data, ".pdf", "doc")
    if doc is None:
        raise _unavailable(
            "Conversion PDF -> DOC impossible sur ce poste ; conservez l'export PDF natif.",
            errors, "doc", 409,
        )
    return doc


__all__: list[str] = [
    "can_convert_formats",
    "doc_to_pdf_bytes",
    "docx_to_doc_bytes",
    "office_to_docx_bytes",
    "pdf_to_doc_bytes",
    "pdf_to_docx_bytes",
    "word_available",
]
