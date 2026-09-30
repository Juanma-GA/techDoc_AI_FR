"""Heuristics for note and callout blocks in legacy documents."""

from __future__ import annotations

import re
import unicodedata

_NOTE_RE = re.compile(
    r"^\s*(?:n\.?\s*b\.?|note|nota|remarque|a\s+noter|important|important\s+note)\s*[:.-]?\s*",
    re.IGNORECASE,
)
_BACKGROUND_RE = re.compile(
    r"^\s*(?:background|contexte|pour\s+information|information\s+generale|a\s+savoir)\s*[:.-]?\s*",
    re.IGNORECASE,
)

_HUMAN_HARM_RE = re.compile(
    r"\b(?:blessure|blessures|brulure|brulures|electrocution|electrique|"
    r"choc\s+electrique|electrocute|intoxication|exposition|mort|mortel|"
    r"danger\s+pour|sous\s+tension|surface\s+chaude|pieces?\s+rotatives?)\b",
    re.IGNORECASE,
)
_MATERIAL_HARM_RE = re.compile(
    r"\b(?:endommage|endommager|endommagement|dommage|dommages|degat|"
    r"degats|casse|casser|corrosion|surtension|deterior|deterioration|"
    r"mauvais\s+fonctionnement|perte\s+de\s+reglage|poussiere|humidite)\b",
    re.IGNORECASE,
)


def detect_note_kind(text: str) -> str | None:
    """Return the normalized admonition kind for a note or contextual callout."""
    if _NOTE_RE.match(text or ""):
        return "note"
    if _BACKGROUND_RE.match(text or ""):
        return "note"
    return None


def classify_admonition(text: str, *, pictogram: bool = False) -> tuple[str | None, float, str]:
    """Classe un callout selon ses signaux semantiques, avec fallback prudent."""
    normalized = unicodedata.normalize("NFKD", text or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = " ".join(normalized.casefold().split())
    if re.match(r"^\s*(warning|avertissement|danger)\b", normalized):
        return "warning", 0.98, "Marqueur textuel explicite de danger humain."
    if re.match(r"^\s*(caution|attention|mise en garde)\b", normalized):
        return "caution", 0.8, "Marqueur textuel explicite de risque materiel; a verifier selon le contenu."
    if re.match(r"^\s*(note|nota|remarque)\b", normalized):
        return "note", 0.98, "Marqueur textuel explicite d'information."
    if _HUMAN_HARM_RE.search(normalized):
        return "warning", 0.92, "Signal de blessure, choc electrique ou danger pour une personne."
    if _MATERIAL_HARM_RE.search(normalized):
        return "caution", 0.82, "Signal de dommage possible pour un equipement ou un composant."
    if pictogram:
        if "garantie" in normalized:
            return "note", 0.45, "Pictogramme present, mais le texte traite surtout de garantie sans danger identifie."
        return "warning", 0.45, "Pictogramme d'attention sans signal textuel suffisamment precis; verification humaine requise."
    return None, 0.0, ""
