"""Vision checks — Mistral multimodal analysis of embedded illustrations.

Emits `RawSuggestion` entries with `rule_kind="vision"` so the rest of
        images = extract_images(src_path, max_per_doc=max_images + 1)
identically to text-bearing rules.

Two checks run per image (cap at 20 images per document) :

    if len(images) > max_images:
        _mark_vision_limited(warnings)
        images = images[:max_images]
- **FIGURE_NO_CAPTION** (structural, no Mistral call) : the PDF doesn't
    contain a « Figure N — … » line below the image. Detection-only —
  the operator has to add the caption in the source document.
- **FIGURE_COHERENCE** (Mistral, requires `vision.enabled` + API key) :
    the image description provided by the multimodal model is compared against the
  caption / surrounding text. A low coherence score raises a warning.

A future iteration can plug in the `regles_conformite_visuelle` rule
catalogue (one JSON entry per yes/no question) — the API
`check_figure_compliance` is already in `mistral_vision` and emits
suggestions one rule per failure.
"""

from __future__ import annotations

import structlog
from sqlalchemy.orm import Session

from app.checks.raw import RawSuggestion
from app.core.errors import AppError
from app.core.mistral_vision import check_figure_compliance, describe_image
from app.parsers.pdf_parser import extract_images


_logger = structlog.get_logger(__name__)


# Built-in vision compliance rules — covers S1000D §5.2 conventions on
# figures. Each rule is asked of the multimodal model as a yes/no question. The
# `id` ends up in the suggestion's `rule_code` so the reviewer can
# filter / toggle the rule like any other catalog entry.
_BUILTIN_VISION_RULES = [
    {
        "id": "FIGURE_HAS_NUMBERING",
        "question": (
            "L'illustration porte-t-elle un repère de numérotation lisible "
            "(« 1 », « 2 », … ou flèches/callouts identifiables) ?"
        ),
        "severity": "info",
    },
    {
        "id": "FIGURE_LEGIBLE",
        "question": (
            "Les éléments principaux de l'illustration sont-ils nets et "
            "lisibles (pas de flou, pas de pixelisation excessive) ?"
        ),
        "severity": "warning",
    },
    {
        "id": "FIGURE_ORIENTATION",
        "question": (
            "L'orientation et le cadrage de l'illustration sont-ils "
            "appropriés pour une publication technique de maintenance ?"
        ),
        "severity": "info",
    },
]


def run(
    db: Session,
    src_path: str,
    *,
    max_images: int = 20,
    enable_mistral: bool = True,
    warnings: list[str] | None = None,
) -> list[RawSuggestion]:
    """Extract every embedded image and emit vision-related suggestions.

    `enable_mistral=False` runs only the structural check
    (FIGURE_NO_CAPTION) — useful when the user just wants the caption
    audit without paying for vision calls."""
    try:
        images = extract_images(src_path, max_per_doc=max_images + 1)
    except Exception as exc:  # noqa: BLE001
        _logger.warning("vision_extract_failed", error=type(exc).__name__)
        _mark_vision_incomplete(warnings)
        return []
    if len(images) > max_images:
        _mark_vision_limited(warnings)
        images = images[:max_images]

    out: list[RawSuggestion] = []
    for idx, img in enumerate(images, start=1):
        # Structural — does the PDF contain a caption near this image ?
        if not img.caption_nearby:
            out.append(
                RawSuggestion(
                    rule_kind="vision",
                    rule_code="FIGURE_NO_CAPTION",
                    severity="warning",
                    message=(
                        f"Figure {idx} sans légende détectable à proximité. "
                        "S1000D §5.2 : la balise <figure> doit contenir un <title>."
                    ),
                    original="",
                    proposed="",  # detection-only
                    page=img.page,
                    span=(0, 0),
                )
            )

        if not enable_mistral:
            continue

        # Semantic compliance — yes/no questions to the multimodal model on the image.
        try:
            result = check_figure_compliance(db, img.bytes, _BUILTIN_VISION_RULES)
        except AppError as exc:
            _logger.warning(
                "vision_compliance_skipped",
                page=img.page, img=idx, code=exc.code,
            )
            _mark_vision_incomplete(warnings)
            continue
        except Exception as exc:  # noqa: BLE001
            _logger.warning("vision_compliance_error", error=type(exc).__name__)
            _mark_vision_incomplete(warnings)
            continue

        for entry in result.get("results", []):
            if not isinstance(entry, dict):
                continue
            if entry.get("compliant") is False:
                rule_id = entry.get("id", "FIGURE_UNKNOWN")
                rule = next(
                    (r for r in _BUILTIN_VISION_RULES if r["id"] == rule_id),
                    {"severity": "warning", "question": rule_id},
                )
                evidence = (entry.get("evidence") or "").strip()
                out.append(
                    RawSuggestion(
                        rule_kind="vision",
                        rule_code=rule_id,
                        severity=str(rule.get("severity") or "warning"),
                        message=(
                            f"Figure {idx} — non-conforme : {rule.get('question', '')}\n"
                            f"Constat vision : {evidence or '(aucune justification)'}"
                        ),
                        original="",
                        proposed="",  # detection-only
                        page=img.page,
                        span=(0, 0),
                        ai_generated=True,
                    )
                )

        # Bonus check — describe vs caption coherence (only if a caption
        # was found and the image is small enough to fit in one request).
        if img.caption_nearby:
            try:
                desc = describe_image(db, img.bytes)
            except Exception as exc:  # noqa: BLE001
                _logger.warning("vision_description_skipped", error=type(exc).__name__)
                _mark_vision_incomplete(warnings)
                continue
            if desc and _looks_incoherent(desc, img.caption_nearby):
                out.append(
                    RawSuggestion(
                        rule_kind="vision",
                        rule_code="FIGURE_COHERENCE",
                        severity="info",
                        message=(
                            f"Figure {idx} — la légende et le contenu visuel "
                            "semblent discordants.\n"
                            f"Légende : {img.caption_nearby}\n"
                            f"Image : {desc}"
                        ),
                        original="",
                        proposed="",
                        page=img.page,
                        span=(0, 0),
                        ai_generated=True,
                    )
                )

    return out


def _mark_vision_incomplete(warnings: list[str] | None) -> None:
    warning = "La vérification sémantique des figures est indisponible; la couverture est réduite."
    if warnings is not None and warning not in warnings:
        warnings.append(warning)


def _mark_vision_limited(warnings: list[str] | None) -> None:
    warning = "La limite d'illustrations a été atteinte; les images restantes n'ont pas été analysées."
    if warnings is not None and warning not in warnings:
        warnings.append(warning)


def _looks_incoherent(description: str, caption: str) -> bool:
    """Cheap heuristic — caption keywords should overlap with the
    description. Returns True when no meaningful word from the caption
    appears in the description (sign of a possible swap)."""
    import re as _re

    tokens = {w.lower() for w in _re.findall(r"\b[\wÀ-ÿ]{5,}\b", caption)}
    if not tokens:
        return False
    desc_low = description.lower()
    overlap = sum(1 for t in tokens if t in desc_low)
    return overlap == 0
