"""Telechargement paresseux + registration de la police Inter pour exports.

reportlab a besoin de fichiers TTF physiques pour utiliser une police custom.
On telecharge Inter-Regular.ttf et Inter-Bold.ttf depuis le repo Google Fonts
(URL stable, OFL) une seule fois, dans `app/assets/fonts/`. Si la connexion
echoue (offline, proxy strict), `ensure_inter()` renvoie False et le caller
fallback sur Helvetica.

Pour python-docx pas besoin de TTF physique : Word substitue cote client.
"""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path
from typing import Optional


log = logging.getLogger("doc_writer.fonts")


FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

_INTER_SOURCES = {
    "Inter-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/static/Inter-Regular.ttf",
    "Inter-Bold.ttf":    "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/static/Inter-Bold.ttf",
}

# Taille minimale plausible d'un TTF Inter (en bytes). En dessous on considere
# que le fichier est corrompu ou tronque (proxy HTML interceptee, etc.).
_MIN_TTF_SIZE = 50_000

# Cache du resultat de ensure_inter() : on ne tente le download qu'une fois.
_registered: Optional[bool] = None


def _download(url: str, dest: Path, timeout: float = 8.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read()
    except Exception as e:  # noqa: BLE001
        log.warning("Inter download failed for %s : %s", url, e)
        return False
    if len(data) < _MIN_TTF_SIZE:
        log.warning("Inter download for %s too small (%d bytes)", url, len(data))
        return False
    dest.write_bytes(data)
    return True


def _ensure_files() -> bool:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in _INTER_SOURCES.items():
        path = FONTS_DIR / name
        if path.is_file() and path.stat().st_size >= _MIN_TTF_SIZE:
            continue
        if not _download(url, path):
            return False
    return True


def ensure_inter() -> bool:
    """Garantit que Inter est register dans reportlab. Lazy : download tente
    au premier appel uniquement. Renvoie False si fallback Helvetica
    necessaire (offline, proxy, etc.).
    """
    global _registered
    if _registered is not None:
        return _registered
    if not _ensure_files():
        log.info("Inter TTF indisponible, PDF utilisera Helvetica en fallback")
        _registered = False
        return False
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        from reportlab.pdfbase.ttfonts import TTFont

        pdfmetrics.registerFont(TTFont("Inter", str(FONTS_DIR / "Inter-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("Inter-Bold", str(FONTS_DIR / "Inter-Bold.ttf")))
        registerFontFamily("Inter", normal="Inter", bold="Inter-Bold")
    except Exception as e:  # noqa: BLE001
        log.warning("reportlab Inter registration failed: %s", e)
        _registered = False
        return False
    _registered = True
    return True
