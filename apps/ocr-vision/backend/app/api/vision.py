"""POST /api/v1/vision/test — OCR + reconnaissance d'image (Mistral).

Cœur de l'app OCR Vision : envoie une image (ou un PDF) aux modèles Mistral et
renvoie le texte transcrit (OCR via `/v1/ocr`) + une description du contenu
(modèle multimodal). OCR et reconnaissance sont indépendants : si l'un échoue,
l'autre peut quand même remonter.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.mistral_client import MistralClient, MistralError
from app.db.session import get_db


router = APIRouter(prefix="/vision", tags=["vision"])

_DESC_PROMPT = (
    "Décris en français ce que montre cette image : objets, équipements, "
    "schémas, pictogrammes, texte visible. Réponds en 3 à 5 phrases."
)


@router.post("/test")
def vision_test(
    file: UploadFile = File(...),
    prompt: str = Form(""),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        client = MistralClient.from_db(db)
    except MistralError as exc:
        raise AppError("MISTRAL_NOT_CONFIGURED", str(exc), status_code=400) from exc

    data = file.file.read()
    if not data:
        raise AppError("FILE_EMPTY", "Fichier vide.", status_code=400)

    name = (file.filename or "").lower()
    if name.endswith(".pdf"):
        mime = "application/pdf"
    else:
        ctype = (file.content_type or "").lower()
        mime = ctype if ctype.startswith("image/") else "image/png"

    ocr_text, description, errors = "", "", []

    try:
        ocr_text = client.ocr(data, mime_type=mime)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"OCR : {type(exc).__name__}: {exc}")

    # Prompt fourni par l'utilisateur pour guider l'analyse, sinon le défaut.
    desc_prompt = prompt.strip() or _DESC_PROMPT

    # La reconnaissance multimodale ne s'applique pas à un PDF.
    if mime != "application/pdf":
        try:
            description = client.describe_image(data, mime_type=mime, prompt=desc_prompt)
        except Exception:  # noqa: BLE001
            # Le modèle vision configuré peut être absent du déploiement →
            # repli sur le modèle chat (multimodal sur Mistral récent).
            try:
                description = client.describe_image(
                    data, mime_type=mime, prompt=desc_prompt, model=client.chat_model
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Reconnaissance : {type(exc).__name__}: {exc}")

    if errors and not ocr_text and not description:
        raise AppError(
            "VISION_FAILED",
            "Le traitement a échoué — " + " ; ".join(errors),
            status_code=502,
        )

    return {
        "ocr_text": (ocr_text or "").strip(),
        "description": (description or "").strip(),
        "warning": " ; ".join(errors),
    }
