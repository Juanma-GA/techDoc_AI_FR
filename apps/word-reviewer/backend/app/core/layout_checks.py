"""Prototype de controles GEOMETRIQUES sur le PDF fidele (PyMuPDF).

Contrairement aux regles semantiques (sur le .docx), ces controles exploitent la
POSITION reelle du texte apres rendu : alignement, centrage, position des pieds
de page. Deux regles pour valider l'approche sur de vrais documents :

- LAYOUT_TITLE_CENTER : un titre (police nettement plus grande, ligne courte) dont
  le centre s'ecarte trop du centre de page.
- LAYOUT_FOOTER       : pied de page absent sur une page, ou dont la position
  horizontale varie d'une page a l'autre.

Chaque finding porte ses bbox en % (origine haut-gauche) pour le surlignage front.
Les seuils sont volontairement simples : a ajuster sur les vrais fichiers.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

log = logging.getLogger("word_reviewer.layout_checks")

# Seuils (en % de la dimension de page) — a affiner sur les vrais documents.
_TITLE_SIZE_RATIO = 1.2      # police "titre" = >= 1.2x la mediane du corps
_TITLE_MAX_WIDTH = 70.0      # une ligne titre couvre < 70% de la largeur
_CENTER_TOL = 6.0            # tolerance de centrage (% largeur)
_FOOTER_BAND_TOP = 90.0      # bande "pied de page" = y0 > 90% hauteur
_FOOTER_ALIGN_TOL = 8.0      # variation max de x du pied entre pages (% largeur)
_MAX_FINDINGS = 60


@dataclass
class _Line:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float  # police max de la ligne


@dataclass
class LayoutFinding:
    id: str
    rule_code: str
    severity: str
    message: str
    page: int
    boxes: list[dict] = field(default_factory=list)


def _lines_of(page: fitz.Page) -> list[_Line]:
    out: list[_Line] = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            xs0 = min(s["bbox"][0] for s in spans)
            ys0 = min(s["bbox"][1] for s in spans)
            xs1 = max(s["bbox"][2] for s in spans)
            ys1 = max(s["bbox"][3] for s in spans)
            size = max((s.get("size", 0.0) for s in spans), default=0.0)
            out.append(_Line(text, xs0, ys0, xs1, ys1, size))
    return out


def _looks_like_title(text: str) -> bool:
    """Distingue un vrai titre d'un fragment a grosse police mais non-titre
    (numero ATA « 34-20-12 », marqueur « TP 2 », date « APR 22/26 », note « * … »).

    Heuristique : un titre porte du texte alphabetique consistant. On exige au
    moins 6 lettres et on ecarte les lignes commencant par une puce/asterisque
    (notes de bas de page). Cela ecarte les codes/nombres/dates courts sans
    rejeter les titres mono-mot (« GENERAL », « HIGHLIGHTS »)."""
    t = text.strip()
    if not t or t[0] in "*•-–—·":
        return False
    letters = sum(1 for c in t if c.isalpha())
    return letters >= 6


def _pct_box(x0: float, y0: float, x1: float, y1: float, w: float, h: float) -> dict:
    return {
        "left": round(100 * x0 / w, 3),
        "top": round(100 * y0 / h, 3),
        "width": round(100 * (x1 - x0) / w, 3),
        "height": round(100 * (y1 - y0) / h, 3),
    }


def analyze_layout(pdf: Path) -> list[LayoutFinding]:
    doc = fitz.open(str(pdf))
    try:
        findings: list[LayoutFinding] = []
        footer_centers: list[tuple[int, float, _Line]] = []  # (page, center_x %, line)
        n = 0

        for i in range(doc.page_count):
            page = doc.load_page(i)
            w = page.rect.width or 1
            h = page.rect.height or 1
            lines = _lines_of(page)
            if not lines:
                continue
            median_size = statistics.median([ln.size for ln in lines if ln.size > 0] or [0])

            # --- Regle 1 : titres non centres ---
            for ln in lines:
                if median_size <= 0 or ln.size < _TITLE_SIZE_RATIO * median_size:
                    continue
                if 100 * (ln.x1 - ln.x0) / w >= _TITLE_MAX_WIDTH:
                    continue  # ligne pleine largeur = pas un titre isole
                if 100 * ln.y0 / h > _FOOTER_BAND_TOP:
                    continue  # ligne en bas de page = pied, pas un titre
                if not _looks_like_title(ln.text):
                    continue  # numero ATA / date / marqueur / note -> pas un titre
                center_pct = 100 * ((ln.x0 + ln.x1) / 2) / w
                offset = abs(center_pct - 50.0)
                if offset > _CENTER_TOL:
                    n += 1
                    findings.append(
                        LayoutFinding(
                            id=f"layout-{n}",
                            rule_code="LAYOUT_TITLE_CENTER",
                            severity="warning",
                            message=f"Titre non centre (decale de {offset:.0f}% du centre) : « {ln.text[:60]} »",
                            page=i + 1,
                            boxes=[_pct_box(ln.x0, ln.y0, ln.x1, ln.y1, w, h)],
                        )
                    )
                    if n >= _MAX_FINDINGS:
                        return findings

            # --- Collecte pied de page (bande basse) ---
            footer_lines = [ln for ln in lines if 100 * ln.y0 / h > _FOOTER_BAND_TOP]
            if not footer_lines:
                n += 1
                findings.append(
                    LayoutFinding(
                        id=f"layout-{n}",
                        rule_code="LAYOUT_FOOTER",
                        severity="warning",
                        message=f"Pied de page absent (page {i + 1}).",
                        page=i + 1,
                        boxes=[],
                    )
                )
            else:
                fl = footer_lines[0]
                footer_centers.append((i + 1, 100 * ((fl.x0 + fl.x1) / 2) / w, fl))
            if n >= _MAX_FINDINGS:
                return findings

        # --- Regle 2b : coherence de position des pieds entre pages ---
        if len(footer_centers) >= 2:
            centers = [c for _, c, _ in footer_centers]
            ref = statistics.median(centers)
            for page_no, c, fl in footer_centers:
                if abs(c - ref) > _FOOTER_ALIGN_TOL:
                    n += 1
                    page = doc.load_page(page_no - 1)
                    w = page.rect.width or 1
                    h = page.rect.height or 1
                    findings.append(
                        LayoutFinding(
                            id=f"layout-{n}",
                            rule_code="LAYOUT_FOOTER",
                            severity="info",
                            message=f"Pied de page mal aligne (page {page_no}, {abs(c - ref):.0f}% d'ecart).",
                            page=page_no,
                            boxes=[_pct_box(fl.x0, fl.y0, fl.x1, fl.y1, w, h)],
                        )
                    )
                    if n >= _MAX_FINDINGS:
                        break
        return findings
    finally:
        doc.close()
