"""Routes /api/v1/brex - profils BREX projet (uploades une fois, reutilises).

Un BREX est defini par projet et applique a tous ses documents : c'est ce qui
evite de refaire le mapping a chaque migration.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from lxml import etree
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.brex_profile import inspect_brex, normalize_brex_upload
from app.core.demo_mode import is_demo_mode
from app.core.errors import AppError
from app.core.s1000d_schema import SUPPORTED_ISSUES
from app.db.models import BrexProfile, Document
from app.db.session import get_db, storage_directory
from app.schemas import (
    BrexObjectValueOut,
    BrexProfileDetailOut,
    BrexProfileOut,
    BrexRuleOut,
    UnsupportedBrexRuleOut,
)

router = APIRouter(prefix="/brex", tags=["brex"])


def _storage(db: Session) -> Path:
    p = storage_directory(db)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _to_out(b: BrexProfile) -> BrexProfileOut:
    return BrexProfileOut(
        id=b.id, name=b.name, s1000d_issue=b.s1000d_issue,
        created_at=b.created_at.isoformat(),
    )


def _profile_xml(b: BrexProfile) -> str:
    path = Path(b.xml_path)
    if not path.is_file():
        raise AppError("BREX_FILE_NOT_FOUND", "Le fichier du profil BREX est introuvable.", 404)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AppError("BREX_FILE_UNREADABLE", "Le fichier du profil BREX est illisible.", 500) from exc


def _to_detail(b: BrexProfile) -> BrexProfileDetailOut:
    try:
        profile = inspect_brex(_profile_xml(b))
    except etree.XMLSyntaxError as exc:
        raise AppError("BAD_BREX", f"Le profil BREX n'est pas lisible : {exc}", 422) from exc
    if not profile.dm_code:
        raise AppError("BREX_DMC_NOT_FOUND", "Le DMC du BREX utilisateur est introuvable.", 422)
    return BrexProfileDetailOut(
        **_to_out(b).model_dump(),
        dmc=profile.dmc,
        dm_code=profile.dm_code,
        rules=[
            BrexRuleOut(
                rule_id=rule.rule_id,
                object_path=rule.object_path,
                allowed_flag=rule.allowed_flag,
                object_use=rule.object_use,
                object_values=[
                    BrexObjectValueOut(
                        value_allowed=value.value_allowed,
                        value_text=value.value_text,
                        value_form=value.value_form,
                        value_tailoring=value.value_tailoring,
                    )
                    for value in rule.object_values
                ],
                rules_context=rule.rules_context,
                context_id=rule.context_id,
                severity_level=rule.severity_level,
                supported=rule.supported,
                support_status=rule.support_status,
                support_reason=rule.support_reason,
            )
            for rule in profile.rules
        ],
        unsupported_rules=[
            UnsupportedBrexRuleOut(
                rule_type=rule.rule_type,
                rule_id=rule.rule_id,
                description=rule.description,
            )
            for rule in profile.unsupported_rules
        ],
    )


@router.get("", response_model=list[BrexProfileOut])
def list_brex(db: Session = Depends(get_db)) -> list[BrexProfileOut]:
    rows = db.scalars(select(BrexProfile).order_by(BrexProfile.created_at.desc())).all()
    return [_to_out(b) for b in rows]


@router.delete("/{brex_id}")
def delete_brex(
    brex_id: str,
    confirm_token: str = Query(""),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if len(confirm_token) < 10:
        raise AppError(
            "DELETE_NOT_CONFIRMED",
            "Suppression non confirmée. Utilisez le double-clic de confirmation.",
            422,
        )
    profile = db.get(BrexProfile, brex_id)
    if profile is None:
        raise AppError("BREX_NOT_FOUND", "Profil BREX inconnu.", 404)
    document_id = db.scalar(
        select(Document.id).where(Document.brex_id == brex_id).limit(1)
    )
    if document_id is not None:
        raise AppError(
            "BREX_IN_USE",
            "Le profil BREX est utilisé par un document et ne peut pas être supprimé.",
            409,
        )

    xml_path = Path(profile.xml_path)
    db.delete(profile)
    db.commit()
    try:
        xml_path.unlink(missing_ok=True)
    except OSError as exc:
        raise AppError(
            "BREX_FILE_DELETE_FAILED",
            "Le profil BREX a été supprimé, mais son fichier XML n'a pas pu être supprimé.",
            500,
        ) from exc
    return {"id": brex_id, "status": "deleted"}


@router.get("/{brex_id}", response_model=BrexProfileDetailOut)
def get_brex(brex_id: str, db: Session = Depends(get_db)) -> BrexProfileDetailOut:
    profile = db.get(BrexProfile, brex_id)
    if profile is None:
        raise AppError("BREX_NOT_FOUND", "Profil BREX inconnu.", 404)
    return _to_detail(profile)


@router.post("", response_model=BrexProfileOut, status_code=201)
async def upload_brex(
    file: UploadFile = File(...),
    name: str = Form(...),
    s1000d_issue: str = Form("4.2"),
    db: Session = Depends(get_db),
) -> BrexProfileOut:
    if is_demo_mode(db):
        raise AppError("DEMO_BREX_DISABLED", "Les profils BREX ne sont pas disponibles en mode démo.", 409)
    if s1000d_issue not in SUPPORTED_ISSUES:
        raise AppError("BAD_ISSUE", f"Issue non supportee : {s1000d_issue}", 422)
    raw = await file.read()
    if len(raw) > settings.max_upload_size_bytes:
        raise AppError("FILE_TOO_LARGE", "Fichier BREX trop volumineux.", 413)
    try:
        xml, parsed = normalize_brex_upload(raw)
    except etree.XMLSyntaxError as exc:
        raise AppError(
            "BAD_BREX",
            f"Le BREX n'est pas un XML lisible dans l'encodage qu'il declare : {exc}",
            422,
        ) from exc
    if not parsed.dm_code:
        raise AppError("BREX_DMC_NOT_FOUND", "Le DMC du BREX utilisateur est introuvable.", 422)
    profile_issue = parsed.issue or s1000d_issue
    if profile_issue not in SUPPORTED_ISSUES:
        schema_detail = (
            f" Schema declare : {parsed.schema_location}."
            if parsed.schema_location
            else ""
        )
        raise AppError(
            "BAD_ISSUE",
            f"Issue BREX non supportee : {profile_issue}.{schema_detail}",
            422,
        )

    profile = BrexProfile(name=name, s1000d_issue=profile_issue, xml_path="")
    db.add(profile)
    db.flush()  # genere l'id
    path = _storage(db) / f"brex_{profile.id}.xml"
    path.write_text(xml, encoding="utf-8")
    profile.xml_path = str(path)
    db.commit()
    return _to_out(profile)
