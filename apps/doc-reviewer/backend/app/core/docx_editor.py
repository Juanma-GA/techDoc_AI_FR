"""Application d'une correction dans un .docx (python-docx).

Localise le bloc cible par son `target_id` (`dp<N>`) via le **walker partage**
`iter_doc_paragraphs` (meme ordre qu'au parsing), puis remplace l'occurrence du
texte. Le formatage du paragraphe est preserve : le texte resultant est ecrit
dans le 1er run (qui porte la mise en forme dominante) et les runs suivants sont
vides — suffisant pour les corrections textuelles (termes, footer, copyright).
"""

from __future__ import annotations

import io

from docx import Document  # type: ignore[import-untyped]
from docx.text.paragraph import Paragraph  # type: ignore[import-untyped]

from app.parsers.docx_parser import iter_doc_paragraphs


def _find_nth(haystack: str, needle: str, occurrence: int) -> int:
    start = 0
    idx = -1
    for _ in range(occurrence + 1):
        idx = haystack.find(needle, start)
        if idx < 0:
            return -1
        start = idx + len(needle)
    return idx


def _rewrite(paragraph: Paragraph, new_full: str) -> None:
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(new_full)
        return
    runs[0].text = new_full
    for r in runs[1:]:
        r.text = ""


def _norm_ws(s: str) -> str:
    """Espaces normalises (collapse + strip) pour un appariement tolerant."""
    return " ".join(s.split())


def _replace_in_paragraph(paragraph: Paragraph, original: str, proposed: str, occurrence: int) -> bool:
    if not original:
        return False
    full = "".join(r.text for r in paragraph.runs)
    idx = _find_nth(full, original, occurrence)
    if idx < 0:
        idx = full.find(original)
    if idx >= 0:
        _rewrite(paragraph, full[:idx] + proposed + full[idx + len(original):])
        return True
    # Repli tolerant aux espaces : si `original` represente tout le paragraphe
    # (a la normalisation des espaces pres), on reecrit le paragraphe entier.
    # Couvre les corrections LLM "bloc complet" ou l'extraction differe d'un
    # espace insecable / d'un retour de ligne.
    if _norm_ws(original) and _norm_ws(original) == _norm_ws(full):
        _rewrite(paragraph, proposed)
        return True
    return False


def apply_to_target(
    data: bytes, target_id: str, original: str, proposed: str, occurrence: int = 0
) -> tuple[bytes, bool]:
    """Applique `original`->`proposed` dans le bloc `target_id`. Retourne (octets, modifie)."""
    doc = Document(io.BytesIO(data))
    changed = False
    for index, _zone, _kind, _ctx, paragraph in iter_doc_paragraphs(doc):
        if f"dp{index}" == target_id:
            changed = _replace_in_paragraph(paragraph, original, proposed, occurrence)
            break
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue(), changed


def apply_group(data: bytes, original: str, proposed: str) -> tuple[bytes, int]:
    """Applique `original`->`proposed` sur **toutes** les occurrences du document."""
    if not original:
        return data, 0
    doc = Document(io.BytesIO(data))
    count = 0
    for _index, _zone, _kind, _ctx, paragraph in iter_doc_paragraphs(doc):
        if not paragraph.runs:
            continue
        full = "".join(r.text for r in paragraph.runs)
        occurrences = full.count(original)
        if occurrences:
            _rewrite(paragraph, full.replace(original, proposed))
            count += occurrences
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue(), count
