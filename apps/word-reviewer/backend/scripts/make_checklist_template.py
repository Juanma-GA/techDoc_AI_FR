"""Genere un modele de checklist Excel pour l'import de regles de revue.

Structure ideale (colonnes) attendue par l'import (`core/excel_rules.py`) :

  | Topic | Regles | Type | Severite | Zone | Contexte |

- **Topic**    -> categorie (regroupement). Une cellule fusionnee vaut pour
  toutes les lignes en-dessous (report automatique).
- **Regles**   -> la regle en langage naturel. **Indispensable.**
- **Type**     -> `manuel` (verification humaine, item de checklist coche a la
  main, PAS d'IA) ou `auto` (evaluee par Mistral). Defaut : auto.
- **Severite** -> error / warning / info. Absente -> deduite du verbe.
- **Zone**     -> cible la verif : footer / header / lep / highlights... (option).
- **Contexte** -> precision libre, concatenee a la regle (option).

Usage :
    python scripts/make_checklist_template.py
    # -> app/static/checklist_template.xlsx
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

# Regles d'exemple : un bloc « manuel » (comme les checklists reelles) + des
# regles « auto » evaluees par l'IA, montrant zone et contexte.
# (topic, regle, type, severite, zone, contexte)
EXAMPLE_RULES: list[tuple[str, str, str, str, str, str]] = [
    ("verif manuel", "Verification manuelle de prise en compte des notes techniques",
     "manuel", "warning", "", ""),
    ("verif manuel", "Verification manuelle de prise en compte des SB avec ou sans impact",
     "manuel", "warning", "", ""),
    ("verif manuel", "Verification manuelle de prise en compte des PE avec ou sans impact",
     "manuel", "warning", "", ""),
    ("En-tete", "Le pied de page doit mentionner la mention de copyright de l'editeur.",
     "auto", "error", "footer", ""),
    ("Illustrations", "Chaque figure doit porter un numero et une legende.",
     "auto", "warning", "", "Controle visuel des figures"),
    ("Terminologie", "Les abreviations devraient etre definies a leur premiere occurrence.",
     "auto", "info", "", ""),
]

HEADERS = ["Topic", "Regles", "Type", "Severite", "Zone", "Contexte"]


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

    # Fusionne la cellule Topic du bloc « verif manuel » (3 lignes) pour coller
    # aux checklists reelles (report du topic sur les lignes fusionnees).
    ws.merge_cells("A2:A4")

    widths = {"A": 16, "B": 70, "C": 10, "D": 10, "E": 12, "F": 28}
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
