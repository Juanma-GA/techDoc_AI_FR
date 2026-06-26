"""Générateur de fixtures FTM — 100 % synthétiques, consolidées par famille de
règle du moteur v4 (cf. `app/checks/`).

Produit, dans ce dossier, trois classeurs réutilisables :

- `referentiel_demo.xlsx`  : suivi ATM + BASL. L'en-tête de l'onglet ATM est en
                             ligne 3 (pas la plus large) → sert la fonction
                             « choisir la ligne d'en-tête » du mapping.
- `fiche_conforme.xlsx`    : fiche qui passe les checks déterministes (aucune
                             anomalie attendue, hors checks IA / référentiel).
- `fiche_non_conforme.xlsx`: fiche qui déclenche AU MOINS une anomalie par
                             famille déterministe (voir `EXPECTED_TYPES`).

Format `.xlsx` (et non `.xlsm`) : openpyxl ne sait pas écrire un `.xlsm`
valide sans `vbaProject.bin` — Excel refuserait alors de l'ouvrir. Les parsers
FTM (`parse_any`, `reference._open`) traitent `.xlsx` et `.xlsm` à l'identique,
donc le format ne change rien aux checks ; les vraies fiches métier restent en
`.xlsm`.

Aucune donnée réelle : tous les contenus sont inventés. Régénérer après une
évolution des règles : `python tests/fixtures/build_fixtures.py`.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

FIXTURES_DIR = Path(__file__).resolve().parent

# Types d'anomalies que `fiche_non_conforme.xlsm` doit faire émettre par le
# pipeline déterministe (sans Mistral ni référentiel). Sert d'oracle au test.
EXPECTED_TYPES = {
    "script",           # script.py        — préfixe DMC-TG5- non respecté
    "texte",            # text_rules.py    — espace de tête / point manquant / début non-verbe
    "ordre_taches",     # text_rules.py    — cellule vide / doublon / saut de numéro
    "tache_induite",    # text_rules.py    — tâche appelée sans référence induite
    "securite",         # operations.py    — phrase de mise en sécurité absente
    "preliminaire",     # operations.py    — sans pression d'air sans isolation pneumatique
    "complementaire",   # operations.py    — contre-action / test manquant
    "serrage",          # operations.py    — couple sans écrimétal
    "valeur_numerique",  # operations.py    — tolérance hors format / valeur sans unité
    "illustration",     # illustration.py  — repère hors format RepXX(FigZZ)
    "rechange",         # referentiel_items.py — doublon / multi-ligne / absent de la tâche
    "outillage",        # referentiel_items.py — outillage du récap absent de la tâche
    "entete",           # referentiel_items.py — champ d'en-tête du récap absent
}


def _append_sheet(wb: Workbook, title: str, rows: list[list[str]], first: bool) -> None:
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    for row in rows:
        ws.append(row)


# ---------------------------------------------------------------------------
# Référentiel (suivi ATM + BASL)
# ---------------------------------------------------------------------------

def build_referentiel(dest: Path) -> Path:
    wb = Workbook()
    # Onglet ATM : en-tête en LIGNE 3 (ligne 1 = titre, ligne 2 = vide), alors
    # que les lignes de données sont plus larges → la détection auto se trompe,
    # ce qui justifie le choix manuel de la ligne d'en-tête (header_row=3).
    atm_rows: list[list[str]] = [
        ["Suivi ATM FTM — extrait synthetique"],
        [],
        ["Script", "Granule defaut", "Granule pose", "Commentaire", "Statut"],
    ]
    # 24 lignes de données synthétiques (DMC-TG5-xxxx) — volume réaliste pour
    # l'aperçu et le mapping de colonnes.
    statuts = ("a valider", "valide", "en cours", "rejete")
    for i in range(1, 25):
        atm_rows.append([
            f"DMC-TG5-{i:04d}",
            f"G-DEF-{i:03d}",
            f"G-POSE-{i:03d}",
            f"Tache de maintenance synthetique {i}",
            statuts[i % len(statuts)],
        ])
    _append_sheet(wb, "Suivi ATM FTM", atm_rows, first=True)

    # BASL : libellés de référence des rechanges / outillages / infrastructures.
    basl_rows: list[list[str]] = [["Designation", "Reference", "Type"]]
    rechanges = [
        ("Joint torique 12mm", "JT-12", "rechange"),
        ("Joint torique 16mm", "JT-16", "rechange"),
        ("Vis CHC M6", "VIS-CHC-M6", "rechange"),
        ("Vis CHC M8", "VIS-CHC-M8", "rechange"),
        ("Ecrou H M8", "ECR-H-M8", "rechange"),
        ("Rondelle plate M8", "RON-M8", "rechange"),
        ("Cle dynamometrique", "OUT-DYN-01", "outillage"),
        ("Cle plate 13mm", "OUT-CLE-13", "outillage"),
        ("Extracteur a inertie", "OUT-EXT-02", "outillage"),
        ("Etabli mobile", "INF-ETA-01", "infrastructure"),
        ("Pont elevateur", "INF-PON-01", "infrastructure"),
    ]
    basl_rows.extend([list(r) for r in rechanges])
    _append_sheet(wb, "BASL", basl_rows, first=False)
    wb.save(dest)
    return dest


# ---------------------------------------------------------------------------
# Fiche conforme — doit passer les checks déterministes
# ---------------------------------------------------------------------------

def build_fiche_conforme(dest: Path) -> Path:
    # NB : les règles matchent le français ACCENTUÉ exact (phrases de mise en
    # sécurité, champs d'en-tête). On respecte donc l'accentuation. L'en-tête
    # « Ordre » est court (≥ 12 car. + minuscules = « opération » au sens du
    # check texte) et le script vit sur un onglet dédié, pour ne pas être pris
    # pour des opérations sans point final.
    wb = Workbook()
    _append_sheet(wb, "En-tete", [
        ["Script : DMC-TG5-AB12"],
    ], first=True)
    _append_sheet(wb, "Tâche de maintenance", [
        ["Ordre", "Opération"],
        ["1", "Appliquer impérativement les procédures de sécurité en vigueur sur le lieu de l'intervention."],
        ["2", "Immobiliser la rame."],
        ["3", "S'assurer de porter les EPI adaptés afin de se prémunir des risques."],
        ["4", "Déposer le carter de protection."],
        ["5", "Contrôler visuellement l'état du joint torique 12mm."],
        ["6", "Tester le fonctionnement de l'équipement."],
        ["7", "Reposer le carter de protection."],
        ["8", "Voir Rep1(Fig1) sur le schéma de montage."],
    ], first=False)
    # Récapitulatif : tous les champs d'en-tête présents + rechange reporté
    # dans la tâche (« joint torique 12mm » figure à l'opération 5).
    _append_sheet(wb, "Récapitulatif", [
        ["ALC", "LCN", "Id_tâche", "désignation", "Période tâche", "Réf_période tâche"],
        ["Rechange", "Quantité"],
        ["Joint torique 12mm", "1"],
    ], first=False)
    wb.save(dest)
    return dest


# ---------------------------------------------------------------------------
# Fiche non conforme — une anomalie par famille
# ---------------------------------------------------------------------------

def build_fiche_non_conforme(dest: Path) -> Path:
    wb = Workbook()
    _append_sheet(wb, "Tâche de maintenance", [
        ["Script : DMC-TG3-9999"],                                  # script: mauvais préfixe
        ["Ordre des tâches", "Opération", "Tâche induite"],
        ["1", " Déposer le carter.", ""],                           # texte: espace en début
        ["2", "Le carter doit être contrôlé", ""],                  # texte: début non-verbe + point manquant
        ["3", "Serrer la vis au couple de 12 N.m", ""],             # serrage: couple sans écrimétal + point manquant
        ["", "Nettoyer la zone de travail.", ""],                   # ordre_taches: cellule vide
        ["5", "Travailler sans pression d'air sur le circuit.", ""],  # preliminaire: pas d'isolation pneumatique
        ["5", "Consigner électriquement la rame.", ""],             # ordre_taches: doublon + complementaire: pas de déconsignation
        ["7", "Mesurer un jeu de 10 à 12 mm.", ""],                 # ordre_taches: saut 5->7 + valeur_numerique: tolérance hors format
        ["8", "Régler le couple à 3,5 puis vérifier.", ""],         # valeur_numerique: valeur décimale sans unité
        ["9", "Voir le repère Rep 12 sur le schéma.", "tâche n 4"],  # illustration: repère hors format
        ["10", "Reposer l'ensemble après dépose.", ""],             # complementaire: pose/dépose sans test équipement
    ], first=True)
    # Récapitulatif : doublon, multi-rechange/ligne, rechange & outillage
    # absents de la tâche, et AUCUN champ d'en-tête (entete).
    _append_sheet(wb, "Récapitulatif", [
        ["Rechange", "Quantité"],
        ["Vis CHC M8", "4"],
        ["Vis CHC M8", "2"],                                        # rechange: doublon
        ["Écrou H M8; Rondelle plate M8", "8"],                     # rechange: plusieurs sur une ligne + absent de la tâche
        ["Outillage", "Référence"],
        ["Clé dynamométrique spéciale", "1"],                       # outillage: absent de la tâche
    ], first=False)
    wb.save(dest)
    return dest


def build_all(out_dir: Path = FIXTURES_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "referentiel": build_referentiel(out_dir / "referentiel_demo.xlsx"),
        "conforme": build_fiche_conforme(out_dir / "fiche_conforme.xlsx"),
        "non_conforme": build_fiche_non_conforme(out_dir / "fiche_non_conforme.xlsx"),
    }


if __name__ == "__main__":
    paths = build_all()
    for name, p in paths.items():
        print(f"{name:14s} -> {p}")
