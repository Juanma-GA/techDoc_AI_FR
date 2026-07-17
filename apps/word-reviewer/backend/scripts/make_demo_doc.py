"""Genere un document de DEMO qui declenche les regles deterministes ATA100 +
les controles geometriques, pour une demonstration fiable (independante du LLM).

Usage : python scripts/make_demo_doc.py [chemin_sortie.docx]
Par defaut : apps/word-reviewer/demo_anomalies.docx
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH


def build(out: Path) -> None:
    d = Document()

    # Titre volontairement ALIGNE A GAUCHE (grande police) -> LAYOUT_TITLE_CENTER.
    h = d.add_heading("MANUEL DE MAINTENANCE - TYPE OF ATTACK SENSOR GIT 3R", level=0)
    h.alignment = WD_ALIGN_PARAGRAPH.LEFT

    d.add_heading("1. GENERALITES", level=1)
    # ATA_CHAPTER_REF : reference pointee (separateurs incorrects) -> 34-10-42.
    d.add_paragraph("Pour la depose, voir la reference 34.10.42 ainsi que 21/30/00.")
    # ATA_CHAPTER_RANGE : chapitre hors plage 00-99.
    d.add_paragraph("Chapter 250 covers the attack sensor installation.")
    # ATA_NO_AMBIGUOUS_QUANT : quantificateurs ambigus.
    d.add_paragraph("There are several parts to inspect and some items may remain loose.")
    d.add_paragraph("Il reste plusieurs points a controler avant la mise en service.")
    # ATA_TORQUE_DUAL_UNIT : couple sans double unite.
    d.add_paragraph("Serrer la vis a 25 Nm, puis verifier le couple de 18 lbft.")

    d.add_heading("2. CONTACT", level=1)
    # Numero de telephone : NE DOIT PAS etre flagge (correctif faux positif).
    d.add_paragraph("THALES - 78990 Menghac - France")
    d.add_paragraph("Tel : +33 (0)5 24 44 77 40 - www.thalesgroup.com")

    d.add_heading("3. NOMENCLATURE", level=1)
    d.add_paragraph("PART NUMBER : 45150320, C14080AA, C16291AB.")
    d.add_paragraph("Reference correcte a conserver : 34-10-42 (deja bien formee).")

    # Pas de pied de page defini -> LAYOUT_FOOTER (pied absent).
    out.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(out))
    print(f"Demo genere : {out}")
    print("Anomalies attendues : ATA_CHAPTER_REF (x2), ATA_CHAPTER_RANGE, "
          "ATA_NO_AMBIGUOUS_QUANT (x3), ATA_TORQUE_DUAL_UNIT (x2), "
          "LAYOUT_TITLE_CENTER, LAYOUT_FOOTER. Le telephone ne doit PAS etre flagge.")


if __name__ == "__main__":
    default = Path(__file__).resolve().parents[2] / "demo_anomalies.docx"
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    build(target)
