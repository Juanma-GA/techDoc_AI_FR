"""Genere un modele de checklist Excel pour l'import de regles personnalisees.

Structure ideale (colonnes) attendue par l'import
(`core/checklist_excel.py`) :

  | Sujet        | Verification (regle en langage naturel)        | Criticite |
  |--------------|------------------------------------------------|-----------|
  | <categorie>  | <consigne evaluee par l'IA sur chaque document> | low/medium/high |

- **Sujet**  -> `label` de la regle (categorie libre, regroupement).
- **Verification** -> `consigne` : la regle exprimee en langage naturel, telle
  quelle utilisee comme prompt Mistral. C'est la colonne indispensable.
- **Criticite** (optionnelle) : low / medium / high. Absente -> deduite du
  verbe (doit/interdit -> high ; devrait/recommande -> low ; sinon medium).

Astuce : un placeholder `{nom_de_colonne}` dans la consigne est remplace a
l'analyse par les valeurs de la colonne de reference homonyme du projet.

Usage :
    python scripts/make_checklist_template.py
    # -> app/static/checklist_template.xlsx
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

# 5 regles d'exemple, generiques (relecture documentaire). La 2e montre le
# placeholder de colonne de reference `{glossaire}`. Type `auto` partout :
# corpus-agent evalue par IA (les lignes « manuel » seraient ignorees a l'import).
# (sujet, verification, type, criticite, zone, contexte)
EXAMPLE_RULES: list[tuple[str, str, str, str, str, str]] = [
    ("Securite",
     "Chaque tache presentant un risque doit indiquer les equipements de protection individuelle (EPI) requis.",
     "auto", "high", "", ""),
    ("Terminologie",
     "Les termes techniques employes doivent appartenir au glossaire de reference : {glossaire}.",
     "auto", "medium", "", "Le placeholder {glossaire} lit la colonne de reference homonyme du projet"),
    ("Structure",
     "Chaque procedure doit comporter une section « Verifications finales » en fin de document.",
     "auto", "medium", "", ""),
    ("Redaction",
     "Les instructions doivent etre redigees a l'imperatif (voix active), une action par phrase.",
     "auto", "low", "", ""),
    ("References",
     "Toute reference a un document externe doit preciser sa version ou sa date d'edition.",
     "auto", "medium", "", ""),
]

HEADERS = ["Sujet", "Verification", "Type", "Criticite", "Zone", "Contexte"]


def build() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Checklist"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="374151")
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill

    for row in EXAMPLE_RULES:
        ws.append(list(row))

    widths = {"A": 16, "B": 72, "C": 10, "D": 10, "E": 10, "F": 32}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    return wb


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "app" / "static" / "checklist_template.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    build().save(out)
    print(f"Modele ecrit : {out}")


if __name__ == "__main__":
    main()
