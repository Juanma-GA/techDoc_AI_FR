"""Dispatcher de moteur de template : PPTX vs Word, + conversion PDF -> Word.

Le doc-writer accepte trois formats de template :

- **.pptx** : moteur `pptx_template` + `pptx_llm_analysis` (geometrie EMU, SVG).
- **.docx** : moteur `docx_template` (flux de texte, mise en page conservee
  nativement au remplissage en place).
- **.pdf** : un PDF n'est pas editable. On le **convertit en .docx** (via
  `pdf2docx`) une seule fois, en sidecar sur disque, puis on le traite comme un
  template Word. Conversion lazy + cachee : declenchee au 1er acces (analyse de
  zones ou export), reutilisee ensuite.

Toute la couche API (documents/export) passe par `resolve(storage_path)` qui
renvoie `(working_path, TemplateEngine)`. `working_path` est le .pptx/.docx
reellement manipule (pour un PDF : le .docx converti). Les moteurs exposent une
interface uniforme (`extract_zones`, `extract_all_frames`, `build_structure`,
`fill_zones`) pour que documents.py / export.py soient agnostiques du format.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import AppError

log = logging.getLogger("doc_writer.template_format")


# Formats acceptes comme template (a l'upload et dans les guards d'API).
SUPPORTED_TEMPLATE_EXTS = {".pptx", ".docx", ".pdf"}

# Suffixe du sidecar .docx genere a partir d'un PDF.
_PDF_DOCX_SIDECAR = ".converted.docx"


@dataclass
class TemplateEngine:
    """Interface uniforme d'un moteur de template (pptx ou docx)."""

    kind: str  # "pptx" | "docx"
    out_ext: str  # extension de l'export rempli ("pptx" | "docx")
    extract_zones: Callable[[str], list]  # type: ignore[type-arg]
    extract_all_frames: Callable[[str], list]  # type: ignore[type-arg]
    build_structure: Callable[[str], dict]
    fill_zones: Callable[..., bytes]


def _ext(path: str) -> str:
    return Path(path).suffix.lower()


def is_supported_template(filename: str) -> bool:
    return _ext(filename) in SUPPORTED_TEMPLATE_EXTS


def _pptx_engine() -> TemplateEngine:
    from app.core import pptx_llm_analysis as pa
    from app.core import pptx_template as pt

    return TemplateEngine(
        kind="pptx",
        out_ext="pptx",
        extract_zones=pt.extract_zones,
        extract_all_frames=pa.extract_all_frames,
        build_structure=pa.build_structure,
        fill_zones=pt.fill_zones,
    )


def _docx_engine() -> TemplateEngine:
    from app.core import docx_template as dx

    return TemplateEngine(
        kind="docx",
        out_ext="docx",
        extract_zones=dx.extract_zones,
        extract_all_frames=dx.extract_all_frames,
        build_structure=dx.build_structure,
        fill_zones=dx.fill_zones,
    )


def _convert_pdf_to_docx(pdf_path: str, docx_path: str) -> None:
    """Convertit un PDF en .docx via pdf2docx. Leve AppError si la lib manque
    ou si la conversion echoue (PDF scanne / protege / corrompu)."""
    try:
        from pdf2docx import Converter  # type: ignore[import-untyped]
    except ImportError as e:  # pragma: no cover - depend de l'install
        raise AppError(
            "PDF_CONVERT_UNAVAILABLE",
            "La conversion PDF -> Word necessite la dependance 'pdf2docx' "
            "(absente). Installe-la (pip install pdf2docx) ou fournis un "
            ".docx / .pptx comme template.",
            status_code=500,
        ) from e
    cv = Converter(pdf_path)
    try:
        cv.convert(docx_path)
    except Exception as e:  # noqa: BLE001
        raise AppError(
            "PDF_CONVERT_FAILED",
            "La conversion PDF -> Word a echoue. Le PDF est peut-etre scanne "
            "(image sans texte), protege, ou de structure trop complexe. "
            f"Detail : {type(e).__name__}: {e}",
            status_code=422,
            detail={"pdf": Path(pdf_path).name},
        ) from e
    finally:
        cv.close()


def working_template_path(storage_path: str) -> str:
    """Chemin du .pptx/.docx reellement manipule.

    - .pptx / .docx : le fichier lui-meme.
    - .pdf : le sidecar `<stem>.converted.docx` (converti a la 1re demande,
      reutilise ensuite). La conversion ne lit jamais que le PDF de
      l'utilisateur, jamais ne le modifie.
    """
    ext = _ext(storage_path)
    if ext in {".pptx", ".docx"}:
        return storage_path
    if ext == ".pdf":
        src = Path(storage_path)
        sidecar = src.with_name(src.stem + _PDF_DOCX_SIDECAR)
        if not sidecar.exists():
            log.info("Conversion PDF -> Word : %s", src.name)
            _convert_pdf_to_docx(str(src), str(sidecar))
        return str(sidecar)
    raise AppError(
        "UNSUPPORTED_TEMPLATE",
        f"Format de template non supporte : {ext}. Formats acceptes : "
        f"{sorted(SUPPORTED_TEMPLATE_EXTS)}.",
        status_code=400,
        detail={"extension": ext},
    )


def engine_for(storage_path: str) -> TemplateEngine:
    """Moteur correspondant au format de template (apres conversion PDF)."""
    ext = _ext(working_template_path(storage_path))
    if ext == ".pptx":
        return _pptx_engine()
    return _docx_engine()


def resolve(storage_path: str) -> tuple[str, TemplateEngine]:
    """`(working_path, engine)` : le chemin a manipuler + son moteur. Declenche
    la conversion PDF si necessaire."""
    working = working_template_path(storage_path)
    ext = _ext(working)
    return working, (_pptx_engine() if ext == ".pptx" else _docx_engine())
