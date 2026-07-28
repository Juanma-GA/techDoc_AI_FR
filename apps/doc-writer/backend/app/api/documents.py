"""Routes /api/v1/documents — upload, list, delete."""

from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.core.indexer import index_document
from app.core.mistral_client import MistralClient, MistralError, get_llm_enabled
from app.core.security import read_and_validate, safe_storage_join
from app.core.template_format import is_supported_template
from app.core.versioning import sha256_of_bytes
from app.db.models import Document
from app.db.session import get_db
from app.parsers import SUPPORTED_EXTS, parse_any
from app.schemas import (
    DocumentContentOut,
    DocumentOut,
    FlowBlock,
    FlowCell,
    FlowOut,
    StructureBbox,
    StructureOut,
    StructureShape,
    StructureSlide,
    UploadItemResult,
    UploadResultOut,
    ZoneIn,
    ZoneOut,
    ZonePatch,
    ZonesBulkDeleteIn,
    ZonesOut,
    ZonesValidateIn,
)

log = logging.getLogger("doc_writer.documents")

router = APIRouter(prefix="/documents", tags=["documents"])

# Liste blanche stricte : on connaît la liste de formats supportés.
ALLOWED_DOC_EXTS = SUPPORTED_EXTS


VALID_KINDS = {"source", "template", "style"}


@router.get("", response_model=list[DocumentOut])
def list_documents(
    kind: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Document]:
    """List documents. Optional `?kind=source|template|style` filter."""
    stmt = select(Document).order_by(Document.uploaded_at.desc())
    if kind:
        if kind not in VALID_KINDS:
            raise AppError(
                "INVALID_KIND",
                f"kind doit etre dans {sorted(VALID_KINDS)}",
                status_code=400,
                detail={"kind": kind},
            )
        stmt = stmt.where(Document.kind == kind)
    return list(db.scalars(stmt))


@router.post("", response_model=UploadResultOut)
def upload_documents(
    files: list[UploadFile] = File(...),
    kind: str = Form(default="source"),
    db: Session = Depends(get_db),
) -> UploadResultOut:
    """Upload N fichiers : valide, dedup sha256, parse, index synchrone.

    Le champ `kind` (form data) indique l'usage :
      - `source` (defaut) : contenu input pour le RAG
      - `template` : structure avec `{{placeholders}}` a remplir
      - `style` : exemple de syntaxe / ton a reproduire

    Si Mistral n'est pas configuré, on enregistre quand même le fichier
    (parsing OK) mais on note `index_error` ; l'indexation n'est faite que
    pour les docs `kind=source` (les templates et styles sont juste lus en
    entier au moment de la generation).
    """
    if kind not in VALID_KINDS:
        raise AppError(
            "INVALID_KIND",
            f"kind doit etre dans {sorted(VALID_KINDS)}",
            status_code=400,
            detail={"kind": kind},
        )
    # Interrupteur LLM OFF : on traite comme "non configure" -> mistral=None,
    # le fichier est enregistre/parse mais non indexe (index_error note).
    if not get_llm_enabled(db):
        mistral = None  # type: ignore[assignment]
    else:
        try:
            mistral = MistralClient.from_db(db)
        except MistralError:
            mistral = None  # type: ignore[assignment]

    results: list[UploadItemResult] = []
    for upload in files:
        try:
            raw, safe_name, ext = read_and_validate(
                upload,
                max_size=settings.max_upload_size_bytes,
                allowed_exts=ALLOWED_DOC_EXTS,
            )
        except AppError as exc:
            results.append(
                UploadItemResult(filename=upload.filename or "?", ok=False, error=exc.message)
            )
            continue

        digest = sha256_of_bytes(raw)

        # Dedup : si le même sha256 existe déjà, on signale skipped.
        existing = db.scalar(select(Document).where(Document.sha256 == digest))
        if existing is not None:
            results.append(
                UploadItemResult(
                    filename=safe_name,
                    ok=True,
                    document_id=existing.id,
                    skipped="duplicate",
                    chunk_count=existing.chunk_count,
                )
            )
            continue

        # Storage : data/storage/doc_<uuid>/<digest>_<safe_name>
        storage_root = safe_storage_join(Path(settings.storage_dir), "documents")
        storage_root.mkdir(parents=True, exist_ok=True)
        new_id = uuid.uuid4()
        doc_dir = safe_storage_join(storage_root, f"doc_{new_id}")
        doc_dir.mkdir(parents=True, exist_ok=True)
        stored = safe_storage_join(doc_dir, f"{digest[:12]}_{safe_name}")
        stored.write_bytes(raw)

        try:
            parsed = parse_any(str(stored), mistral=mistral)
            extracted_text = parsed.get("text", "")
        except Exception as e:  # noqa: BLE001
            log.exception("parse failed for %s", safe_name)
            results.append(
                UploadItemResult(
                    filename=safe_name, ok=False, error=f"Parse error: {e}"
                )
            )
            try:
                stored.unlink()
            except OSError:
                pass
            continue

        doc = Document(
            id=new_id,
            filename=safe_name,
            mime_type=upload.content_type or "",
            size=len(raw),
            sha256=digest,
            storage_path=str(stored),
            extracted_text=extracted_text,
            kind=kind,
        )
        db.add(doc)
        db.flush()

        chunk_count = 0
        index_err: str | None = None
        # Indexation RAG uniquement pour les docs source. Les templates et
        # styles sont juste lus en entier au moment de la generation.
        if kind == "source":
            if mistral is not None:
                try:
                    chunk_count = index_document(db, doc, mistral)
                except Exception as e:  # noqa: BLE001
                    log.exception("index failed for %s", safe_name)
                    index_err = f"{type(e).__name__}: {e}"
                    doc.index_error = index_err
                    db.commit()
            else:
                doc.index_error = "MISTRAL_NOT_CONFIGURED"
                db.commit()

        results.append(
            UploadItemResult(
                filename=safe_name,
                ok=True,
                document_id=doc.id,
                chunk_count=chunk_count,
                error=index_err,
            )
        )

    db.commit()
    return UploadResultOut(uploaded=results)


# v2 = ajout `validated`. v1 reste lisible (auto-migre au read avec
# validated auto-calcule depuis dropped_count + len(zones)).
_ZONES_CACHE_KIND_V1 = "zones_v1"
_ZONES_CACHE_KIND_V2 = "zones_v2"
_ZONES_CACHE_KINDS = {_ZONES_CACHE_KIND_V1, _ZONES_CACHE_KIND_V2}


def _zones_to_dicts(zones: list) -> list[dict]:  # type: ignore[type-arg]
    out: list[dict] = []
    for z in zones:
        # Accepte Zone (dataclass) OU dict (relecture du cache + mutation
        # par les endpoints CRUD). `active` defaut True (retrocompat caches
        # ecrits avant l'introduction du champ).
        if isinstance(z, dict):
            out.append({
                "id": z.get("id", ""),
                "kind": z.get("kind", ""),
                "slide_index": int(z.get("slide_index", 0)),
                "slide_title": z.get("slide_title", "") or "",
                "label": z.get("label", "") or "",
                "location": z.get("location", "") or "",
                "target": z.get("target", "") or "",
                "active": bool(z.get("active", True)),
                "instruction": z.get("instruction", "") or "",
                "align": z.get("align", "") or "",
            })
        else:
            out.append({
                "id": z.id,
                "kind": z.kind,
                "slide_index": z.slide_index,
                "slide_title": z.slide_title,
                "label": z.label,
                "location": z.location,
                "target": z.target,
                "active": getattr(z, "active", True),
                "instruction": getattr(z, "instruction", "") or "",
                "align": getattr(z, "align", "") or "",
            })
    return out


def _auto_validated(zones_count: int, dropped_count: int) -> bool:
    """Auto-validation : OK si au moins une zone ET aucun rejet de coherence.
    Sinon, l'utilisateur doit valider manuellement via POST /zones/validate."""
    return zones_count > 0 and dropped_count == 0


def _read_zones_cache(
    doc: Document,
) -> tuple[list[dict] | None, bool, int, bool]:
    """Renvoie (zones_dicts, llm_used, dropped_count, validated). Cache
    absent/invalide -> (None, False, 0, False). v1 auto-migre vers v2 :
    `validated` est calcule depuis `dropped_count` + `len(zones)`."""
    if not doc.extracted_text:
        return None, False, 0, False
    try:
        data = json.loads(doc.extracted_text)
    except json.JSONDecodeError:
        return None, False, 0, False
    if not isinstance(data, dict) or data.get("_kind") not in _ZONES_CACHE_KINDS:
        return None, False, 0, False
    zones = data.get("zones")
    if not isinstance(zones, list):
        return None, False, 0, False
    llm_used = bool(data.get("llm_used", False))
    dropped = int(data.get("dropped_count", 0))
    if data.get("_kind") == _ZONES_CACHE_KIND_V1:
        validated = _auto_validated(len(zones), dropped)
    else:
        validated = bool(data.get("validated", False))
    return zones, llm_used, dropped, validated


def _read_removed(doc: Document) -> list[dict]:  # type: ignore[type-arg]
    """Liste des zones soft-deleted depuis le cache (restaurables). [] si
    absent ou cache invalide."""
    if not doc.extracted_text:
        return []
    try:
        data = json.loads(doc.extracted_text)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    removed = data.get("removed")
    return removed if isinstance(removed, list) else []


def _write_zones_cache(
    doc: Document,
    zones: list,  # type: ignore[type-arg]
    llm_used: bool,
    dropped_count: int,
    db: Session,
    *,
    validated: bool | None = None,
    removed: list | None = None,  # type: ignore[type-arg]
) -> None:
    """Persiste le cache v2. `validated=None` -> auto-calcule. `removed=None`
    -> preserve la liste soft-delete existante (la plupart des operations ne
    la touchent pas) ; passer une liste explicite pour la remplacer."""
    if validated is None:
        validated = _auto_validated(len(zones), dropped_count)
    if removed is None:
        removed = _read_removed(doc)
    doc.extracted_text = json.dumps(
        {
            "_kind": _ZONES_CACHE_KIND_V2,
            "zones": _zones_to_dicts(zones),
            "removed": _zones_to_dicts(removed),
            "llm_used": llm_used,
            "dropped_count": dropped_count,
            "validated": validated,
        },
        ensure_ascii=False,
    )
    db.commit()


def _zones_out(
    cached: list[dict],  # type: ignore[type-arg]
    removed: list[dict],  # type: ignore[type-arg]
    llm_used: bool,
    dropped: int,
    validated: bool,
) -> ZonesOut:
    """Construit la reponse ZonesOut depuis des dicts (zones + corbeille)."""
    return ZonesOut(
        zones=[ZoneOut(**z) for z in cached],
        removed=[ZoneOut(**z) for z in removed],
        llm_used=llm_used,
        dropped_count=dropped,
        validated=validated,
    )


def _compute_zones(
    doc: Document,
    db: Session,
) -> tuple[list, bool, int]:  # type: ignore[type-arg]
    """Calcule les zones (regex deterministes + enumeration des cadres).
    Renvoie (zones, llm_used, dropped_count). Le moteur (pptx ou docx) est
    choisi selon le format du template ; un PDF est converti en .docx en amont
    par `template_format.resolve`."""
    from app.core.template_format import resolve

    working, engine = resolve(doc.storage_path)

    try:
        det_zones = engine.extract_zones(working)
    except AppError:
        raise
    except Exception as e:  # noqa: BLE001
        raise AppError(
            "PARSE_FAILED",
            f"Lecture du template echouee : {type(e).__name__}: {e}",
            status_code=500,
        ) from e

    # Nommage 100% deterministe (texte propre du cadre, ou voisin structurel).
    # Mistral est utilise pour le REMPLISSAGE a l'export, pas pour le nommage.
    llm_used = False
    dropped = 0

    # Enumeration exhaustive des cadres (memes cibles que le selecteur d'ajout
    # manuel via build_structure) : liste complete par defaut, l'utilisateur
    # elague ensuite.
    try:
        frame_zones = engine.extract_all_frames(working)
    except Exception as e:  # noqa: BLE001
        log.warning("frame enumeration failed for %s: %s", doc.id, e)
        frame_zones = []

    return det_zones + frame_zones, llm_used, dropped


@router.get("/{document_id}/zones", response_model=ZonesOut)
def get_zones(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ZonesOut:
    """Liste des zones a remplir detectees dans un template `.pptx`/`.docx`/`.pdf`.

    Trois types de zones :
      - `placeholder` : marqueur explicite `{{cle}}` (deterministe)
      - `xxx` : marqueur libre `XXX` (deterministe ; label devine par contexte)
      - `llm`/`frame` : cadre identifie par enumeration structurelle

    Lecture PURE : renvoie le cache s'il existe, ne le recalcule que s'il est
    absent (1re analyse). Ne fait donc jamais perdre de configuration
    utilisateur. Pour forcer une redetection (fichier modifie) en preservant
    les edits deja faits, voir `POST .../zones/reanalyse`.

    400 si le document n'est pas un template supporte ; 404 si introuvable.
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError(
            "DOCUMENT_NOT_FOUND",
            "Document introuvable.",
            status_code=404,
            detail={"id": str(document_id)},
        )
    if not is_supported_template(doc.filename):
        raise AppError(
            "UNSUPPORTED_TEMPLATE",
            "Seuls les formats .pptx, .docx et .pdf exposent des zones.",
            status_code=400,
            detail={"filename": doc.filename},
        )

    cached, llm_used_cached, dropped_cached, validated_cached = _read_zones_cache(doc)
    if cached is not None:
        return _zones_out(
            cached, _read_removed(doc),
            llm_used_cached, dropped_cached, validated_cached,
        )

    zones, llm_used, dropped = _compute_zones(doc, db)
    # `validated=None` -> auto-validation. La toute premiere analyse d'un
    # template n'a par definition aucune corbeille a preserver.
    _write_zones_cache(doc, zones, llm_used, dropped, db, removed=[])
    cached, llm_used_c, dropped_c, validated_c = _read_zones_cache(doc)
    return _zones_out(cached or [], [], llm_used_c, dropped_c, validated_c)


# Champs d'une zone que seul l'utilisateur edite (label, consigne, activation,
# alignement) : c'est TOUT ce que `reanalyse_zones` doit preserver. Les champs
# structurels (kind, position, titre de slide, libelle d'emplacement) sont eux
# rafraichis a chaque passe, puisqu'ils decrivent l'etat reel du fichier.
_USER_EDITED_ZONE_FIELDS = ("label", "instruction", "active", "align")


def _zone_id_sort_key(zone_id: str) -> int:
    """Suffixe numerique d'un id de zone (`z_12` -> 12, `z_frame_3` -> 3).
    Utilise UNIQUEMENT pour departager des zones qui partagent un `target`
    (cf. `_target_occurrence_map`) : `counter` est incremente en continu
    pendant tout le parcours d'une shape (`extract_zones`/`extract_all_frames`),
    donc les ids des marqueurs d'une MEME shape restent des entiers consecutifs
    dans l'ordre de ses propres paragraphes — meme si la numerotation globale
    bouge ailleurs dans le fichier suite a l'ajout/suppression d'une AUTRE shape.
    """
    m = re.search(r"(\d+)$", zone_id)
    return int(m.group(1)) if m else 0


def _target_occurrence_map(zones: list[dict]) -> dict[tuple[str, int], dict]:  # type: ignore[type-arg]
    """{(target, ordinal): zone} pour les zones ayant un `target` non vide.

    `target` n'identifie PAS un marqueur unique : un meme cadre PPTX/Word peut
    porter plusieurs marqueurs `XXX`/`{{cle}}` (plusieurs paragraphes dans une
    seule shape), qui partagent alors le MEME `target` de niveau shape (cf.
    `Zone.target`). `ordinal` (0-based, tri par id au sein d'un meme target)
    distingue ces marqueurs entre eux, de facon stable d'une passe a l'autre
    tant que l'ORDRE INTERNE de la shape ne change pas — ce qui est le cas
    normal d'une simple reanalyse (le fichier n'a pas restructure CETTE shape).
    """
    by_target: dict[str, list[dict]] = {}
    for z in zones:
        target = z.get("target", "")
        if target:
            by_target.setdefault(target, []).append(z)
    out: dict[tuple[str, int], dict] = {}
    for target, group in by_target.items():
        ordered = sorted(group, key=lambda z: _zone_id_sort_key(z["id"]))
        for ordinal, z in enumerate(ordered):
            out[(target, ordinal)] = z
    return out


def _merge_reanalysed_zones(
    new_zones: list,  # type: ignore[type-arg]  # list[Zone]
    old_zones: list[dict],  # type: ignore[type-arg]
    old_removed: list[dict],  # type: ignore[type-arg]
) -> list[dict]:  # type: ignore[type-arg]
    """Fusionne une redetection complete avec l'etat deja persiste.

    Une zone redetectee dont la cle `(target, ordinal)` (cf.
    `_target_occurrence_map`) correspond a une zone deja connue HERITE de son
    label/consigne/activation/alignement — c'est la seule maniere de distinguer
    « configure par l'utilisateur » de « valeur par defaut de la detection » ;
    la redetection ne doit rafraichir que l'ENSEMBLE des zones (cadres
    ajoutes/supprimes dans le template), jamais la configuration d'une zone qui
    existe encore. Une zone dont la cle est deja a la corbeille est exclue du
    resultat : elle ne doit pas resurgir active simplement parce que la
    redetection la revoit dans le fichier (`reanalyse_zones` preserve la
    corbeille telle quelle a cote de ce resultat).
    """
    new_dicts = _zones_to_dicts(new_zones)

    old_map = _target_occurrence_map(old_zones + old_removed)
    removed_ids = {z["id"] for z in old_removed}
    removed_keys = {key for key, z in old_map.items() if z["id"] in removed_ids}
    key_by_new_id = {z["id"]: key for key, z in _target_occurrence_map(new_dicts).items()}

    merged: list[dict] = []
    for z in new_dicts:
        key = key_by_new_id.get(z["id"])
        if key is not None and key in removed_keys:
            continue
        old = old_map.get(key) if key is not None else None
        if old is not None:
            for field in _USER_EDITED_ZONE_FIELDS:
                z[field] = old[field]
        merged.append(z)
    return merged


@router.post("/{document_id}/zones/reanalyse", response_model=ZonesOut)
def reanalyse_zones(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ZonesOut:
    """Redetecte les zones d'un template apres une modification du fichier
    (cadres ajoutes/supprimes), en PRESERVANT le label/consigne/activation/
    alignement des zones deja configurees par l'utilisateur (fusion par
    `target`, cf. `_merge_reanalysed_zones`) et la corbeille telle quelle.

    Endpoint dedie en POST (et non un GET `?refresh=true`) : l'operation
    modifie l'etat persiste, et un GET ne doit jamais avoir d'effet de bord —
    un simple prefetch ou retry cote client ne doit jamais pouvoir ecraser une
    configuration existante.

    400 si le document n'est pas un template supporte ; 404 si introuvable.
    """
    doc = _require_template(db.get(Document, document_id), document_id)

    old_zones, _, _, _ = _read_zones_cache(doc)
    old_removed = _read_removed(doc)

    zones, llm_used, dropped = _compute_zones(doc, db)
    merged = _merge_reanalysed_zones(zones, old_zones or [], old_removed)

    _write_zones_cache(doc, merged, llm_used, dropped, db, removed=old_removed)
    cached, llm_used_c, dropped_c, validated_c = _read_zones_cache(doc)
    return _zones_out(cached or [], _read_removed(doc), llm_used_c, dropped_c, validated_c)


# ---------------------------------------------------------------------------
# Zones CRUD : add / patch / delete / validate. La source de verite est le
# cache JSON `Document.extracted_text` (v2). Apres toute modif manuelle, le
# flag `validated` est mis a False sauf si l'appelant valide explicitement.
# ---------------------------------------------------------------------------


def _require_template(doc: Document | None, document_id: uuid.UUID) -> Document:
    if doc is None:
        raise AppError(
            "DOCUMENT_NOT_FOUND",
            "Document introuvable.",
            status_code=404,
            detail={"id": str(document_id)},
        )
    if not is_supported_template(doc.filename):
        raise AppError(
            "UNSUPPORTED_TEMPLATE",
            "Seuls les formats .pptx, .docx et .pdf exposent des zones.",
            status_code=400,
            detail={"filename": doc.filename},
        )
    return doc


def _require_zones_loaded(
    doc: Document,
) -> tuple[list[dict], bool, int, bool]:
    """Renvoie l'etat zones du cache. Levee 404 si aucune analyse n'a encore
    ete faite (l'utilisateur doit appeler GET /zones d'abord)."""
    cached, llm_used, dropped, validated = _read_zones_cache(doc)
    if cached is None:
        raise AppError(
            "ZONES_NOT_ANALYSED",
            "Les zones de ce template n'ont pas encore ete analysees. "
            "Lance d'abord une analyse (Reanalyser).",
            status_code=404,
            detail={"id": str(doc.id)},
        )
    return cached, llm_used, dropped, validated


def _next_zone_id(zones: list[dict]) -> str:
    """Genere un nouvel id z_llm_manual_N en evitant les collisions."""
    used = {z.get("id", "") for z in zones}
    n = 1
    while True:
        candidate = f"z_llm_manual_{n}"
        if candidate not in used:
            return candidate
        n += 1


def _validate_align(value: str | None) -> str:
    """Normalise une consigne d'alignement. None -> "". Rejette une valeur hors
    domaine (""|left|center|right|justify) par un 400 explicite."""
    from app.core.pptx_template import ALIGN_VALUES

    val = (value or "").strip()
    if val not in ALIGN_VALUES:
        raise AppError(
            "INVALID_ALIGN",
            "Alignement invalide. Valeurs acceptees : "
            "'' (auto), left, center, right, justify.",
            status_code=400,
            detail={"align": value},
        )
    return val


@router.post("/{document_id}/zones", response_model=ZonesOut)
def add_zone(
    document_id: uuid.UUID,
    payload: ZoneIn,
    db: Session = Depends(get_db),
) -> ZonesOut:
    """Ajoute une zone manuellement. kind force a 'llm' (les zones regex
    viennent du parsing du pptx, pas de l'utilisateur). Apres add,
    `validated` repasse a False : il faut re-valider explicitement."""
    doc = _require_template(db.get(Document, document_id), document_id)
    cached, llm_used, dropped, _validated = _require_zones_loaded(doc)

    # Refus si le target est deja utilise par une zone existante (sinon
    # double-ecriture a fill_zones).
    used_targets = {z.get("target", "") for z in cached if z.get("target")}
    if payload.target in used_targets:
        raise AppError(
            "ZONE_TARGET_USED",
            f"Une zone utilise deja le target '{payload.target}'.",
            status_code=409,
            detail={"target": payload.target},
        )

    new_zone = {
        "id": _next_zone_id(cached),
        "kind": "llm",
        "slide_index": payload.slide_index,
        "slide_title": payload.slide_title,
        "label": payload.label[:200],
        "location": payload.location,
        "target": payload.target,
        "instruction": payload.instruction,
        "align": _validate_align(payload.align),
    }
    cached.append(new_zone)
    _write_zones_cache(doc, cached, llm_used, dropped, db, validated=False)
    return _zones_out(cached, _read_removed(doc), llm_used, dropped, False)


@router.patch("/{document_id}/zones/{zone_id}", response_model=ZonesOut)
def patch_zone(
    document_id: uuid.UUID,
    zone_id: str,
    payload: ZonePatch,
    db: Session = Depends(get_db),
) -> ZonesOut:
    """Met a jour label / target / active d'une zone existante.

    Changement structurel (label, target) -> `validated` repasse a False.
    Simple toggle `active` -> PRESERVE la validation (c'est une preference
    de remplissage, pas une modif de la definition des zones)."""
    doc = _require_template(db.get(Document, document_id), document_id)
    cached, llm_used, dropped, validated = _require_zones_loaded(doc)

    target_zone = next((z for z in cached if z.get("id") == zone_id), None)
    if target_zone is None:
        raise AppError(
            "ZONE_NOT_FOUND",
            f"Zone '{zone_id}' introuvable.",
            status_code=404,
            detail={"zone_id": zone_id},
        )

    structural_change = payload.label is not None or payload.target is not None

    if payload.label is not None:
        target_zone["label"] = payload.label[:200]
    if payload.target is not None:
        # Refus si le nouveau target est deja pris par une AUTRE zone.
        for z in cached:
            if z.get("id") != zone_id and z.get("target") == payload.target:
                raise AppError(
                    "ZONE_TARGET_USED",
                    f"Une autre zone utilise deja le target '{payload.target}'.",
                    status_code=409,
                    detail={"target": payload.target},
                )
        target_zone["target"] = payload.target
    if payload.active is not None:
        target_zone["active"] = payload.active
    if payload.instruction is not None:
        # Consigne = guidage de remplissage, pas une modif de la definition
        # de la zone -> ne reset PAS la validation (comme `active`).
        target_zone["instruction"] = payload.instruction
    if payload.align is not None:
        # Alignement = preference de rendu, non structurel -> preserve la
        # validation (comme `active` / `instruction`).
        target_zone["align"] = _validate_align(payload.align)

    new_validated = False if structural_change else validated
    _write_zones_cache(doc, cached, llm_used, dropped, db, validated=new_validated)
    return _zones_out(cached, _read_removed(doc), llm_used, dropped, new_validated)


@router.delete("/{document_id}/zones/{zone_id}", response_model=ZonesOut)
def delete_zone(
    document_id: uuid.UUID,
    zone_id: str,
    db: Session = Depends(get_db),
) -> ZonesOut:
    """Soft-delete : deplace la zone vers la corbeille (`removed`) au lieu de
    la perdre, pour pouvoir la restaurer ensuite. Preserve la validation (une
    suppression reduit l'ensemble deja revu, elle ne l'invalide pas)."""
    doc = _require_template(db.get(Document, document_id), document_id)
    cached, llm_used, dropped, validated = _require_zones_loaded(doc)

    target_zone = next((z for z in cached if z.get("id") == zone_id), None)
    if target_zone is None:
        raise AppError(
            "ZONE_NOT_FOUND",
            f"Zone '{zone_id}' introuvable.",
            status_code=404,
            detail={"zone_id": zone_id},
        )
    cached = [z for z in cached if z.get("id") != zone_id]
    removed = _read_removed(doc)
    removed = [z for z in removed if z.get("id") != zone_id]  # dedup
    removed.append(target_zone)

    _write_zones_cache(
        doc, cached, llm_used, dropped, db, validated=validated, removed=removed,
    )
    return _zones_out(cached, removed, llm_used, dropped, validated)


@router.post("/{document_id}/zones/validate", response_model=ZonesOut)
def validate_zones(
    document_id: uuid.UUID,
    payload: ZonesValidateIn,
    db: Session = Depends(get_db),
) -> ZonesOut:
    """Toggle manuel du flag `validated` du template. L'export PPTX refuse
    tant que `validated=false` (sauf rattrapage par auto-validation)."""
    doc = _require_template(db.get(Document, document_id), document_id)
    cached, llm_used, dropped, _validated = _require_zones_loaded(doc)
    _write_zones_cache(
        doc, cached, llm_used, dropped, db, validated=payload.validated
    )
    return _zones_out(
        cached, _read_removed(doc), llm_used, dropped, payload.validated,
    )


@router.get("/{document_id}/structure", response_model=StructureOut)
def get_structure(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> StructureOut:
    """Structure complete du template : shapes + positions EMU + dimensions
    du slide. Sert au rendu SVG cote UI et au picker du formulaire
    'Ajouter une zone'."""
    doc = _require_template(db.get(Document, document_id), document_id)

    from app.core.template_format import resolve

    working, engine = resolve(doc.storage_path)
    try:
        struct = engine.build_structure(working)
    except AppError:
        raise
    except Exception as e:  # noqa: BLE001
        raise AppError(
            "PARSE_FAILED",
            f"Lecture du template echouee : {type(e).__name__}: {e}",
            status_code=500,
        ) from e

    slides_out: list[StructureSlide] = []
    for s in struct.get("slides", []):
        sidx = int(s.get("index", 0))
        title = s.get("title", "") or ""
        shapes_out: list[StructureShape] = []
        for sh in s.get("shapes", []):
            bbox_raw = sh.get("bbox")
            bbox_out = StructureBbox(**bbox_raw) if bbox_raw else None
            shapes_out.append(StructureShape(
                id=sh.get("id", ""),
                kind=sh.get("kind", ""),
                slide_index=sidx,
                slide_title=title,
                location=sh.get("location", ""),
                text=sh.get("text", "") or "",
                bbox=bbox_out,
            ))
        slides_out.append(StructureSlide(
            index=sidx,
            title=title,
            shapes=shapes_out,
        ))

    return StructureOut(
        slide_width_emu=int(struct.get("slide_width_emu", 0)),
        slide_height_emu=int(struct.get("slide_height_emu", 0)),
        slides=slides_out,
    )


@router.get("/{document_id}/flow", response_model=FlowOut)
def get_flow(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> FlowOut:
    """Apercu 'flux document' Word/PDF : le document dans l'ordre de lecture
    (paragraphes + tableaux), marqueurs inclus. Pendant du /structure (SVG)
    reserve au PPTX positionne. 400 pour un template PPTX (utiliser /structure)."""
    doc = _require_template(db.get(Document, document_id), document_id)

    from app.core import docx_template
    from app.core.template_format import resolve

    working, engine = resolve(doc.storage_path)
    if engine.kind != "docx":
        raise AppError(
            "FLOW_UNSUPPORTED",
            "L'apercu 'flux' ne concerne que les templates Word/PDF. "
            "Pour un .pptx, utilise /structure (apercu positionne).",
            status_code=400,
            detail={"kind": engine.kind},
        )
    try:
        flow = docx_template.build_flow(working)
    except AppError:
        raise
    except Exception as e:  # noqa: BLE001
        raise AppError(
            "PARSE_FAILED",
            f"Lecture du template echouee : {type(e).__name__}: {e}",
            status_code=500,
        ) from e

    blocks_out: list[FlowBlock] = []
    for b in flow.get("blocks", []):
        rows_out = [
            [
                FlowCell(
                    id=c.get("id", ""),
                    text=c.get("text", "") or "",
                    has_marker=bool(c.get("has_marker", False)),
                )
                for c in row
            ]
            for row in b.get("rows", [])
        ]
        blocks_out.append(FlowBlock(
            type=b.get("type", "paragraph"),
            id=b.get("id", ""),
            location=b.get("location", "") or "",
            text=b.get("text", "") or "",
            has_marker=bool(b.get("has_marker", False)),
            rows=rows_out,
        ))
    return FlowOut(blocks=blocks_out)


@router.post("/{document_id}/zones/bulk-delete", response_model=ZonesOut)
def bulk_delete_zones(
    document_id: uuid.UUID,
    payload: ZonesBulkDeleteIn,
    db: Session = Depends(get_db),
) -> ZonesOut:
    """Soft-delete de plusieurs zones (corbeille). Preserve la validation.
    Les ids inexistants sont ignores silencieusement (idempotent)."""
    doc = _require_template(db.get(Document, document_id), document_id)
    cached, llm_used, dropped, validated = _require_zones_loaded(doc)

    to_delete = set(payload.ids)
    moved = [z for z in cached if z.get("id") in to_delete]
    cached = [z for z in cached if z.get("id") not in to_delete]
    removed = [z for z in _read_removed(doc) if z.get("id") not in to_delete]
    removed.extend(moved)

    _write_zones_cache(
        doc, cached, llm_used, dropped, db, validated=validated, removed=removed,
    )
    return _zones_out(cached, removed, llm_used, dropped, validated)


@router.post(
    "/{document_id}/zones/{zone_id}/restore", response_model=ZonesOut
)
def restore_zone(
    document_id: uuid.UUID,
    zone_id: str,
    db: Session = Depends(get_db),
) -> ZonesOut:
    """Restaure une zone soft-deleted depuis la corbeille vers la liste active.
    404 si la zone n'est pas dans la corbeille. 409 si sa cible est entre-temps
    reprise par une autre zone active."""
    doc = _require_template(db.get(Document, document_id), document_id)
    cached, llm_used, dropped, validated = _require_zones_loaded(doc)
    removed = _read_removed(doc)

    zone = next((z for z in removed if z.get("id") == zone_id), None)
    if zone is None:
        raise AppError(
            "ZONE_NOT_FOUND",
            f"Zone '{zone_id}' absente de la corbeille.",
            status_code=404,
            detail={"zone_id": zone_id},
        )
    # Conflit de cible : seules les zones PAR CIBLE (llm/frame, remplies via
    # une ecriture sur la shape) ne peuvent pas partager un target. Les zones
    # regex (xxx/{{cle}}) sont remplies en inline et peuvent legitimement
    # partager un cadre (plusieurs marqueurs dans la meme text box) -> pas de
    # conflit pour elles.
    _TARGET_KINDS = {"llm", "frame"}
    tgt = zone.get("target", "")
    if (
        tgt
        and zone.get("kind") in _TARGET_KINDS
        and any(
            z.get("target") == tgt and z.get("kind") in _TARGET_KINDS
            for z in cached
        )
    ):
        raise AppError(
            "ZONE_TARGET_USED",
            f"Une zone active utilise deja la cible '{tgt}'.",
            status_code=409,
            detail={"target": tgt},
        )

    removed = [z for z in removed if z.get("id") != zone_id]
    cached.append(zone)
    _write_zones_cache(
        doc, cached, llm_used, dropped, db, validated=validated, removed=removed,
    )
    return _zones_out(cached, removed, llm_used, dropped, validated)


@router.get("/{document_id}/content", response_model=DocumentContentOut)
def get_document_content(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentContentOut:
    """Renvoie le TEXTE EXTRAIT d'un document (ce que le parsing / l'OCR / la
    vision a produit) — pour verifier l'extraction sans ouvrir le fichier.

    Pour un template, `extracted_text` porte le cache des zones (JSON) : on
    re-derive le vrai contenu via `_load_doc_text` (qui re-parse si besoin)."""
    from app.core.writer_engine import _load_doc_text

    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError(
            "DOCUMENT_NOT_FOUND",
            "Document introuvable.",
            status_code=404,
            detail={"id": str(document_id)},
        )
    if doc.kind == "template":
        loaded = _load_doc_text(db, doc.id)
        text = loaded[1] if loaded else ""
    else:
        text = doc.extracted_text or ""
    return DocumentContentOut(
        id=doc.id,
        filename=doc.filename,
        kind=doc.kind,
        char_count=len(text),
        text=text,
    )


@router.post("/{document_id}/reparse", response_model=DocumentOut)
def reparse_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DocumentOut:
    """Re-extrait le texte d'un document DEJA stocke (sans re-upload), via le
    parser courant. Utile apres un changement de moteur de lecture PDF
    (vision / OCR Mistral) : l'extraction est mise en cache a l'upload, ce
    endpoint la rafraichit. Re-indexe (RAG) les documents source.

    Refuse les templates : leur `extracted_text` porte le cache des zones, pas
    du texte brut -> pour eux, utiliser GET /zones?refresh=true.
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError(
            "DOCUMENT_NOT_FOUND",
            "Document introuvable.",
            status_code=404,
            detail={"id": str(document_id)},
        )
    if doc.kind == "template":
        raise AppError(
            "REPARSE_UNSUPPORTED_TEMPLATE",
            "Un template ne se re-extrait pas ici (son texte porte le cache des "
            "zones). Utilise la reanalyse des zones a la place.",
            status_code=400,
            detail={"id": str(document_id), "kind": doc.kind},
        )

    # Interrupteur LLM OFF : pas d'OCR/vision Mistral -> mistral=None, le parsing
    # reste deterministe (extraction texte native uniquement).
    if not get_llm_enabled(db):
        mistral = None  # type: ignore[assignment]
    else:
        try:
            mistral = MistralClient.from_db(db)
        except MistralError:
            mistral = None  # type: ignore[assignment]

    try:
        parsed = parse_any(doc.storage_path, mistral=mistral)
    except Exception as e:  # noqa: BLE001
        log.exception("reparse failed for %s", doc.id)
        raise AppError(
            "PARSE_FAILED",
            f"Re-extraction echouee : {type(e).__name__}: {e}",
            status_code=500,
        ) from e

    doc.extracted_text = parsed.get("text", "")
    doc.index_error = None
    db.flush()

    # Source : re-indexation RAG (index_document est idempotent : purge + recree
    # les chunks, met a jour chunk_count et commit). Style : pas d'index (lu en
    # entier a la generation), on persiste juste le nouveau texte.
    if doc.kind == "source":
        if mistral is not None:
            try:
                index_document(db, doc, mistral)
            except Exception as e:  # noqa: BLE001
                log.exception("reindex failed for %s", doc.id)
                doc.index_error = f"{type(e).__name__}: {e}"
                db.commit()
        else:
            doc.index_error = "MISTRAL_NOT_CONFIGURED"
            db.commit()
    else:
        db.commit()

    db.refresh(doc)
    return DocumentOut.model_validate(doc)


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    doc = db.get(Document, document_id)
    if doc is None:
        raise AppError(
            "DOCUMENT_NOT_FOUND",
            "Document introuvable.",
            status_code=404,
            detail={"id": str(document_id)},
        )

    # Supprime le dossier du document sur disque (best-effort). On retire tout
    # le dossier `doc_<uuid>/` (et pas seulement le fichier) pour emporter les
    # eventuels sidecars generes, ex. le `.converted.docx` d'un template PDF.
    try:
        path = Path(doc.storage_path)
        parent = path.parent
        if parent.exists() and parent.name.startswith("doc_"):
            import shutil

            shutil.rmtree(parent, ignore_errors=True)
        elif path.exists():
            path.unlink()
    except OSError:
        log.warning("could not delete files for %s", doc.id)

    db.delete(doc)
    db.commit()
