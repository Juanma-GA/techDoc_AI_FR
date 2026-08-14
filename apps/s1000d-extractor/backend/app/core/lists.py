"""Conversion des listes a puces d'un texte brut en balisage HTML/XML.

Le texte extrait d'un PDF/Word garde les marqueurs de liste en clair
(`- item`, `1. item`). Cette passe les transforme en structures balisees
(`<ul>/<ol>` + `<li>`), en respectant l'imbrication donnee par l'indentation.
Le reste devient des `<p>`.

Deterministe et sans IA : c'est une transformation de forme, pas de sens.
"""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

from app.core.structure_heuristics import detect_list_kind, strip_list_marker

_INDENT_STEP = 2      # nb d'espaces qui vaut un niveau d'imbrication
_TAG = {"bullet": "ul", "ordered": "ol"}


def _indent_of(line: str) -> int:
    expanded = line.replace("\t", " " * 4)
    return (len(expanded) - len(expanded.lstrip(" "))) // _INDENT_STEP


def _close_to(stack: list[str], out: list[str], depth: int) -> None:
    while len(stack) > depth:
        out.append(f"</{stack.pop()}>")


def parse_lists(text: str) -> str:
    """Convertit les listes a puces/numerotees d'un texte en `<ul>/<ol>/<li>`.

    Les lignes hors liste deviennent des `<p>`. L'imbrication suit l'indentation
    (2 espaces = 1 niveau). Le texte est echappe XML : la sortie est toujours
    un fragment bien forme.
    """
    out: list[str] = []
    stack: list[str] = []          # tags de liste ouverts, du plus externe au plus interne
    kinds: list[str] = []          # "bullet" / "ordered" par niveau ouvert

    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        kind = detect_list_kind(line)
        if kind is None:
            _close_to(stack, out, 0)
            kinds.clear()
            out.append(f"<p>{escape(line.strip())}</p>")
            continue

        # Un item indente de `depth` niveaux vit dans `depth + 1` listes ouvertes.
        target = _indent_of(raw) + 1
        _close_to(stack, out, target)
        del kinds[target:]
        if len(stack) == target and kinds and kinds[-1] != kind:
            # Changement de nature au meme niveau : on ferme et rouvre.
            out.append(f"</{stack.pop()}>")
            kinds.pop()
        while len(stack) < target:
            out.append(f"<{_TAG[kind]}>")
            stack.append(_TAG[kind])
            kinds.append(kind)
        out.append(f"<li>{escape(strip_list_marker(line))}</li>")

    _close_to(stack, out, 0)
    return "".join(out)


_S1000D_LIST = {"ul": "randomList", "ol": "sequentialList", "li": "listItem"}
_LI_RE = re.compile(r"<li>(.*?)</li>", re.DOTALL)


def to_s1000d(fragment: str) -> str:
    """Traduit le fragment HTML de `parse_lists` en vocabulaire S1000D
    (`randomList`/`sequentialList`/`listItem` > `para`)."""
    # Un listItem S1000D ne porte pas de texte nu : son contenu vit dans un para.
    fragment = _LI_RE.sub(r"<li><para>\1</para></li>", fragment)

    def repl(m: re.Match[str]) -> str:
        closing, tag = m.group(1), m.group(2)
        mapped = _S1000D_LIST.get(tag, "para" if tag == "p" else tag)
        return f"<{closing}{mapped}>"

    return re.sub(r"<(/?)(ul|ol|li|p)>", repl, fragment)
