"""Detection des entetes / pieds de page recurrents (bruit de mise en page).

Signal *faible* mais precieux pour hierarchiser : un entete ("MANUEL REF-4521")
ou un pied ("Page 3/12") se repete sur beaucoup de pages, dans une bande haute
ou basse. On le tague `header` / `footer` pour que l'utilisateur puisse
l'exclure (bruit) sans confondre avec du contenu.

Reserve au PDF : seuls les blocs porteurs de geometrie (`y0`/`y1`/`page_height`)
sont analyses. Les blocs DOCX / OCR (sans bbox) restent `body` -> degradation
gracieuse, jamais de faux positif.
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.core.ir import RawBlock

# Bandes haute/basse de la page (ratio de la hauteur). Origine haut-gauche.
_HEADER_MAX = 0.10   # y0/hauteur < 0.10 -> candidat entete
_FOOTER_MIN = 0.90   # y1/hauteur > 0.90 -> candidat pied

# Un numero de page seul ("3", "Page 3", "3 / 12", "- 3 -") -> pied quasi certain.
_PAGE_NUM_RE = re.compile(
    r"^\s*[-–—]?\s*(?:page|p\.?)?\s*\d{1,4}\s*(?:/\s*\d{1,4}|(?:of|sur)\s*\d{1,4})?\s*[-–—]?\s*$",  # noqa: RUF001
    re.IGNORECASE,
)
_DIGITS_WS = re.compile(r"[\d\s\W_]+", re.UNICODE)


def _normalize(text: str) -> str:
    """Cle de repetition : minuscules, chiffres/espaces/ponctuation retires.

    "Page 3" et "Page 4" -> "page" (meme entete a numero variable)."""
    return _DIGITS_WS.sub("", text.lower())


def classify_zones(blocks: list[RawBlock]) -> None:
    """Tague `header` / `footer` sur les RawBlock, en place (PDF uniquement)."""
    geo = [b for b in blocks if b.page_height and b.y0 is not None and b.y1 is not None]
    if not geo:
        return
    n_pages = len({b.page for b in geo if b.page is not None})

    # Repartition des candidats par bande, avec comptage de repetition (cle
    # normalisee -> pages distinctes ou elle apparait).
    top_pages: dict[str, set[int]] = defaultdict(set)
    bot_pages: dict[str, set[int]] = defaultdict(set)
    for b in geo:
        assert b.page_height and b.y0 is not None and b.y1 is not None
        top = b.y0 / b.page_height
        bot = b.y1 / b.page_height
        key = _normalize(b.text)
        if top < _HEADER_MAX and key:
            top_pages[key].add(b.page or 0)
        if bot > _FOOTER_MIN and key:
            bot_pages[key].add(b.page or 0)

    repeat_min = max(2, round(0.5 * n_pages))

    for b in geo:
        assert b.page_height and b.y0 is not None and b.y1 is not None
        top = b.y0 / b.page_height
        bot = b.y1 / b.page_height
        key = _normalize(b.text)
        text = b.text.strip()
        is_page_num = bool(_PAGE_NUM_RE.match(text))
        # Entete/pied = signal de REPETITION : sur une page unique on ne peut pas
        # distinguer un entete recurrent du titre du document -> on ne tague que
        # les numeros de page en pied (motif sur), jamais d'entete "au flair".
        if bot > _FOOTER_MIN and (
            is_page_num or len(bot_pages.get(key, ())) >= repeat_min
        ):
            b.zone = "footer"
        elif top < _HEADER_MAX and key and len(top_pages.get(key, ())) >= repeat_min:
            b.zone = "header"
