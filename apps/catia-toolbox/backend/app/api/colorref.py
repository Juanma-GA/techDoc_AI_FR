"""Routes /api/v1/colorref - referentiel de couleurs (nom -> RGB).

Consomme par l'etape 3 (colorisation SMGXML) : la colonne "Ref Couleur" de la
nomenclature (ex. "Visserie") est resolue en RGB ecrit dans `Actor.Color`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import color_ref
from app.core import texture_ref
from app.db.session import get_db
from app.schemas import ColorRefListIn, ColorRefListOut, TextureConfigIn, TextureConfigOut


router = APIRouter(prefix="/colorref", tags=["colorref"])


@router.get("", response_model=ColorRefListOut)
def get_ref(db: Session = Depends(get_db)) -> ColorRefListOut:
    return ColorRefListOut(entries=color_ref.get_referential(db))


@router.post("", response_model=ColorRefListOut)
def set_ref(payload: ColorRefListIn, db: Session = Depends(get_db)) -> ColorRefListOut:
    saved = color_ref.set_referential(db, [e.model_dump() for e in payload.entries])
    return ColorRefListOut(entries=saved)


@router.get("/texture", response_model=TextureConfigOut)
def get_texture(db: Session = Depends(get_db)) -> TextureConfigOut:
    """Config textures : bibliotheque de styles + extension (.SMGStyleSet)."""
    return TextureConfigOut(**texture_ref.get_texture_config(db))


@router.post("/texture", response_model=TextureConfigOut)
def set_texture(payload: TextureConfigIn, db: Session = Depends(get_db)) -> TextureConfigOut:
    return TextureConfigOut(**texture_ref.set_texture_config(db, payload.library, payload.ext))
