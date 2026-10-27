"""Les sorties LLM affichees a l'utilisateur sont du texte brut, jamais du Markdown."""

from __future__ import annotations

import re

PLAIN_TEXT_RULE_FR = (
    "Réponds en TEXTE BRUT : n'utilise jamais de Markdown (pas de **gras**, "
    "pas de *italique*, pas de titres #, pas de blocs de code ni de backticks)."
)
PLAIN_TEXT_RULE_EN = (
    "Reply in PLAIN TEXT: never use Markdown (no **bold**, no *italics*, "
    "no # headings, no code blocks or backticks)."
)

_FENCE = re.compile(r"^[ \t]*```[^\n]*\n?", re.MULTILINE)
_HEADING = re.compile(r"^[ \t]*#{1,6}[ \t]+", re.MULTILINE)
_BULLET = re.compile(r"^([ \t]*)[*+][ \t]+", re.MULTILINE)
_BOLD = re.compile(r"(\*\*|__)(?=\S)")
_BOLD_END = re.compile(r"(?<=\S)(\*\*|__)")
# Caracteres pouvant etre le debut d'un marqueur coupe entre deux tokens
_HOLD_BACK = "*`#_+"


def _clean(text: str, at_line_start: bool) -> str:
    # Sentinelle : evite qu'un debut de chunk soit pris pour un debut de ligne
    prefix = "\n" if at_line_start else "\0"
    out = prefix + text
    out = _FENCE.sub("", out)
    out = _HEADING.sub("", out)
    out = _BULLET.sub(r"\1- ", out)
    out = _BOLD.sub("", out)
    out = _BOLD_END.sub("", out)
    out = out.replace("**", "").replace("`", "").replace("*", "")
    return out[1:]


def strip_markdown(text: str) -> str:
    """Retire les marqueurs Markdown d'un texte complet."""
    return _clean(text, True)


class PlainTextStream:
    """Filtre de flux : retient la fin d'un chunk si un marqueur peut etre coupe."""

    def __init__(self) -> None:
        self._held = ""
        self._at_line_start = True

    def feed(self, delta: str) -> str:
        text = self._held + delta
        keep = len(text) - len(text.rstrip(_HOLD_BACK))
        self._held = text[len(text) - keep:] if keep else ""
        ready = text[: len(text) - keep] if keep else text
        return self._emit(ready)

    def flush(self) -> str:
        ready, self._held = self._held, ""
        return self._emit(ready)

    def _emit(self, ready: str) -> str:
        if not ready:
            return ""
        cleaned = _clean(ready, self._at_line_start)
        self._at_line_start = ready.endswith("\n")
        return cleaned
