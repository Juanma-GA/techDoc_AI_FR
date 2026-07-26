"""Controles GEOMETRIQUES (layout) sur le PDF fidele (PyMuPDF).

Contrairement aux regles textuelles/structurelles, ces controles exploitent la
POSITION reelle du texte apres rendu : centrage des titres, presence et
alignement des pieds de page, marge gauche du corps. Ils repondent au besoin
« detecter alignements / disposition ».

Chaque finding est un `RawSuggestion` (rule_kind="layout") **detection-only**
(`proposed=""`) portant sa **bbox en points PDF** -> surligne directement dans
le reviewer, sans passer par `search_for`.

Seuils volontairement conservateurs (les majuscules/aeronautique produisent deja
beaucoup de bruit) : a affiner sur de vrais documents.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from app.checks.s1000d_checks import RawSuggestion

log = logging.getLogger("doc_reviewer.layout_checks")

# Seuils (en % de la dimension de page sauf mention).
_TITLE_SIZE_RATIO = 1.2   # police "titre" >= 1.2x la mediane du corps (exclut les titres du check marge)
_FOOTER_BAND_TOP = 90.0   # bande "pied de page" = y0 > 90% hauteur
_FOOTER_ALIGN_TOL = 8.0   # variation max de x du pied entre pages (% largeur)
_MARGIN_TOL = 6.0         # ecart max a la marge gauche dominante (% largeur)
_MARGIN_MIN_LINES = 6     # nb min de lignes de corps pour juger la marge
_MAX_FINDINGS = 80


@dataclass
class _Line:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float


def _lines_of(page: fitz.Page) -> list[_Line]:
    out: list[_Line] = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            x0 = min(s["bbox"][0] for s in spans)
            y0 = min(s["bbox"][1] for s in spans)
            x1 = max(s["bbox"][2] for s in spans)
            y1 = max(s["bbox"][3] for s in spans)
            size = max((s.get("size", 0.0) for s in spans), default=0.0)
            out.append(_Line(text, x0, y0, x1, y1, size))
    return out


def _finding(code: str, severity: str, message: str, page: int,
             box: tuple[float, float, float, float] | None,
             original: str = "") -> RawSuggestion:
    return RawSuggestion(
        rule_kind="layout",
        rule_code=code,
        severity=severity,
        message=message,
        original=original,
        proposed="",  # detection-only : correction manuelle
        page=page,
        span=(0, 0),
        bbox=box,
    )


def run(src_path: str | None) -> list[RawSuggestion]:
    if not src_path or not Path(src_path).is_file():
        return []
    try:
        doc = fitz.open(src_path)
    except Exception as exc:  # noqa: BLE001
        log.warning("layout_open_failed: %s", exc)
        return []
    out: list[RawSuggestion] = []
    footer_centers: list[tuple[int, float, _Line]] = []
    try:
        for i in range(doc.page_count):
            if len(out) >= _MAX_FINDINGS:
                break
            page = doc.load_page(i)
            w = page.rect.width or 1.0
            h = page.rect.height or 1.0
            lines = _lines_of(page)
            if not lines:
                continue
            sizes = [ln.size for ln in lines if ln.size > 0]
            median_size = statistics.median(sizes) if sizes else 0.0

            # NB : la regle « titre non centre » a ete RETIREE — elle supposait
            # qu'un titre doit etre centre, ce qui flaguait a tort chaque titre
            # en MAJUSCULES aligne a gauche (convention frequente en doc
            # technique) -> faux positifs. On ne detecte plus que des ecarts
            # geometriques SANS hypothese de mise en page (pied de page, marge).

            # --- Regle : marge gauche du corps incoherente ---
            body = [
                ln for ln in lines
                if 100 * ln.y0 / h <= _FOOTER_BAND_TOP
                and (median_size <= 0 or ln.size < _TITLE_SIZE_RATIO * median_size)
            ]
            if len(body) >= _MARGIN_MIN_LINES:
                left_ref = statistics.median([100 * ln.x0 / w for ln in body])
                for ln in body:
                    dev = 100 * ln.x0 / w - left_ref
                    # Seul un decalage vers la DROITE (indentation isolee) est
                    # signale ; un retrait a gauche est souvent une liste/titre.
                    if dev > _MARGIN_TOL:
                        out.append(_finding(
                            "LAYOUT_LEFT_MARGIN", "info",
                            f"Ligne desalignee a gauche ({dev:.0f}% de retrait vs la marge).",
                            i + 1, (ln.x0, ln.y0, ln.x1, ln.y1), original=ln.text[:80],
                        ))

            # --- Collecte pied de page ---
            footer_lines = [ln for ln in lines if 100 * ln.y0 / h > _FOOTER_BAND_TOP]
            if not footer_lines:
                out.append(_finding(
                    "LAYOUT_FOOTER", "warning",
                    f"Pied de page absent (page {i + 1}).",
                    i + 1, None,
                ))
            else:
                fl = footer_lines[0]
                footer_centers.append((i + 1, 100 * ((fl.x0 + fl.x1) / 2) / w, fl))

        # --- Regle 3 : coherence de position des pieds entre pages ---
        if len(footer_centers) >= 2 and len(out) < _MAX_FINDINGS:
            ref = statistics.median([c for _, c, _ in footer_centers])
            for page_no, c, fl in footer_centers:
                if abs(c - ref) > _FOOTER_ALIGN_TOL:
                    out.append(_finding(
                        "LAYOUT_FOOTER", "info",
                        f"Pied de page mal aligne (page {page_no}, {abs(c - ref):.0f}% d'ecart).",
                        page_no, (fl.x0, fl.y0, fl.x1, fl.y1),
                    ))
        return out[:_MAX_FINDINGS]
    finally:
        doc.close()
