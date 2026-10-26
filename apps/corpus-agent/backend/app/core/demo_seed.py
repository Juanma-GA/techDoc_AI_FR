"""Projet de demonstration synthetique (mode demo).

Genere en memoire des fiches de maintenance XLSX multi-onglets, entierement
fictives, puis les ingere dans un projet dedie via le chemin d'upload normal.
Aucun fichier utilisateur n'est lu.
"""

from __future__ import annotations

import io
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AnalysisRun, Anomaly, File, FileVersion, Project

DEMO_PROJECT_NAME = "Projet démo - Fiches de maintenance"
DEMO_PROJECT_DESCRIPTION = (
    "Projet synthetique genere par le mode demo : fiches de maintenance fictives "
    "sur plusieurs onglets. Supprime automatiquement a la sortie du mode demo."
)
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_COVER_HEADER = ["Champ", "Valeur"]
_TASK_HEADER = ["N°", "Tâche", "Description", "Durée (min)", "Qualification", "Référence outillage"]
_PARTS_HEADER = ["Réf. pièce", "Désignation", "Quantité", "Unité", "Remplacement"]
_TOOLS_HEADER = ["Réf. outillage", "Désignation", "Calibration requise", "Prochaine calibration"]
_HISTORY_HEADER = ["Révision", "Date", "Auteur", "Modification"]

_SHEETS = (
    (
        "FTM-DEMO-32-10-01.xlsx",
        "32-10-01",
        "Remplacement du verin de train principal",
        [
            ("32-10-01.1", "Preparation", "Depressuriser le circuit hydraulique avant toute intervention.", 20, "B1", "TL-1001"),
            ("32-10-01.2", "Depose", "Deposer le verin en respectant le couple de desserrage du tableau.", 45, "B1", "TL-1002"),
            ("32-10-01.3", "Pose", "Installer le verin neuf et serrer les fixations au couple indique.", 60, "B1", "TL-1002"),
            ("32-10-01.4", "Controle", "Verifier l'etancheite et consigner l'intervention dans le journal de bord.", 30, "B2", ""),
        ],
        [
            ("PN-DEMO-3201", "Verin de train principal", 1, "EA", "Oui"),
            ("PN-DEMO-3202", "Joint d'etancheite", 2, "EA", "Oui"),
            ("PN-DEMO-3203", "Axe de fixation", 2, "EA", "Non"),
        ],
        [
            ("TL-1001", "Manometre hydraulique", "Oui", "2027-03-01"),
            ("TL-1002", "Cle dynamometrique 50-250 Nm", "Oui", "2027-01-15"),
        ],
        [
            ("A", "2026-01-12", "Redacteur demo", "Creation de la fiche"),
            ("B", "2026-04-03", "Redacteur demo", "Ajout de l'etape de controle d'etancheite"),
        ],
    ),
    (
        "FTM-DEMO-21-30-02.xlsx",
        "21-30-02",
        "Inspection du clapet de regulation de pression cabine",
        [
            ("21-30-02.1", "Acces", "Ouvrir le panneau d'acces et securiser la zone.", 15, "B1", ""),
            ("21-30-02.2", "Inspection", "Inspecter visuellement le clapet et mesurer le jeu de fonctionnement.", 40, "B1", "TL-2001"),
            ("21-30-02.3", "Essai", "Realiser l'essai fonctionnel et noter les valeurs relevees.", 35, "B2", "TL-2002"),
        ],
        [
            ("PN-DEMO-2101", "Clapet de regulation", 1, "EA", "Selon inspection"),
            ("PN-DEMO-2102", "Collier de serrage", 4, "EA", "Non"),
        ],
        [
            ("TL-2001", "Jauge d'epaisseur", "Non", ""),
            ("TL-2002", "Banc d'essai pression", "Oui", "2026-12-20"),
        ],
        [
            ("A", "2026-02-20", "Redacteur demo", "Creation de la fiche"),
        ],
    ),
    (
        "FTM-DEMO-24-50-03.xlsx",
        "24-50-03",
        "Remplacement du connecteur de bus electrique",
        [
            ("24-50-03.1", "Consignation", "Mettre le bus hors tension et verifier l'absence de tension.", 25, "B2", "TL-3001"),
            ("24-50-03.2", "Depose", "Deconnecter et deposer le connecteur defectueux.", 30, "B2", ""),
            ("24-50-03.3", "Pose", "Installer le connecteur neuf et serrer au couple prescrit.", 40, "B2", "TL-3002"),
            ("24-50-03.4", "Remise sous tension", "Remettre sous tension et controler la continuite.", 20, "B2", "TL-3001"),
        ],
        [
            ("PN-DEMO-2401", "Connecteur de bus", 1, "EA", "Oui"),
            ("PN-DEMO-2402", "Graisse dielectrique", 1, "TB", "Non"),
        ],
        [
            ("TL-3001", "Multimetre de maintenance", "Oui", "2026-11-30"),
            ("TL-3002", "Tournevis dynamometrique", "Oui", "2027-02-10"),
        ],
        [
            ("A", "2026-03-05", "Redacteur demo", "Creation de la fiche"),
            ("B", "2026-05-18", "Redacteur demo", "Mise a jour des references d'outillage"),
        ],
    ),
)


def _build_workbook(spec: tuple) -> bytes:
    _, task_ref, title, tasks, parts, tools, history = spec
    wb = Workbook()
    cover = wb.active
    cover.title = "Page de garde"
    cover.append(_COVER_HEADER)
    for row in (
        ("Reference", f"FTM-DEMO-{task_ref}"),
        ("Titre", title),
        ("Domaine", "Maintenance - donnees synthetiques"),
        ("Statut", "Brouillon"),
    ):
        cover.append(list(row))
    for name, header, rows in (
        ("Taches", _TASK_HEADER, tasks),
        ("Pieces", _PARTS_HEADER, parts),
        ("Outillage", _TOOLS_HEADER, tools),
        ("Historique", _HISTORY_HEADER, history),
    ):
        sheet = wb.create_sheet(name)
        sheet.append(header)
        for row in rows:
            sheet.append(list(row))
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# Anciennete (jours) de chaque analyse : le nombre d'anomalies par analyse
# diminue (8, 5, 3, 2) pour illustrer l'amelioration de la conformite du corpus.
_RUN_AGES = (21, 14, 7, 1)

# Motifs de rejet des anomalies demo, indexes par (fichier, analyse, categorie)
_REJECTION_MOTIFS = {
    (1, 0, "Qualification"): "Faux positif : la qualification est definie dans la page de garde.",
    (2, 0, "Historique"): "Hors perimetre : l'auteur de la verification est tracé dans le SGDT.",
    (2, 1, "Qualification"): "Deja couvert : qualification B2 validee par la revue technique.",
}


def _anomaly_specs() -> list[tuple]:
    # (fichier, analyse, categorie, severite, confiance, statut, message, suggestion, onglet/cellule)
    return [
        # Analyse 0 : etat initial du corpus (8 anomalies)
        (0, 0, "Securite", "high", "elevee", "fixed", "L'avertissement de depressurisation n'est pas repete avant l'etape de depose.", "Ajouter l'avertissement avant l'etape 32-10-01.2.", "Taches / 32-10-01.2"),
        (0, 0, "Outillage", "medium", "elevee", "fixed", "L'outillage TL-1002 est cite sans valeur de couple.", "Renseigner le couple de serrage dans la description.", "Taches / 32-10-01.3"),
        (0, 0, "Pieces", "medium", "moyenne", "fixed", "La piece PN-DEMO-3203 n'a pas d'indication de remplacement coherente avec la tache.", "Verifier la colonne Remplacement.", "Pieces / PN-DEMO-3203"),
        (1, 0, "Outillage", "medium", "elevee", "fixed", "La jauge TL-2001 ne precise pas sa calibration.", "Indiquer la calibration requise.", "Outillage / TL-2001"),
        (1, 0, "Qualification", "low", "moyenne", "rejected", "La qualification de l'etape d'essai n'est pas alignee avec la page de garde.", "Harmoniser les qualifications.", "Taches / 21-30-02.3"),
        (2, 0, "Securite", "high", "elevee", "fixed", "L'absence de tension n'est pas verifiee avec un outil reference.", "Citer TL-3001 dans la verification.", "Taches / 24-50-03.1"),
        (2, 0, "Historique", "low", "faible", "rejected", "La revision B ne mentionne pas l'auteur de la verification.", "Ajouter le verificateur.", "Historique / B"),
        (2, 0, "Pieces", "medium", "elevee", "acknowledged", "La graisse dielectrique n'a pas de quantite exprimee en unite coherente.", "Preciser la quantite en grammes.", "Pieces / PN-DEMO-2402"),
        # Analyse 1 (5 anomalies)
        (0, 1, "Securite", "high", "elevee", "fixed", "Aucune mention de consignation avant l'intervention hydraulique.", "Ajouter une etape de consignation.", "Taches / 32-10-01.1"),
        (1, 1, "Pieces", "medium", "moyenne", "fixed", "Le remplacement du clapet est conditionnel sans critere d'acceptation.", "Ajouter le critere de rebut.", "Pieces / PN-DEMO-2101"),
        (1, 1, "Securite", "high", "moyenne", "acknowledged", "La zone n'est pas balisee avant l'essai en pression.", "Ajouter une mise en garde avant l'essai.", "Taches / 21-30-02.3"),
        (2, 1, "Outillage", "medium", "elevee", "fixed", "Le couple de serrage du connecteur n'est pas precise.", "Indiquer la valeur de couple.", "Taches / 24-50-03.3"),
        (2, 1, "Qualification", "low", "moyenne", "rejected", "La qualification B2 n'est pas justifiee pour l'etape de depose.", "Confirmer la qualification requise.", "Taches / 24-50-03.2"),
        # Analyse 2 (3 anomalies)
        (0, 2, "Historique", "low", "faible", "fixed", "La revision B n'indique pas de reference de modification.", "Completer la colonne Modification.", "Historique / B"),
        (1, 2, "Securite", "high", "moyenne", "open", "L'essai en pression ne rappelle pas la limite de pression maximale.", "Citer la pression maximale autorisee.", "Taches / 21-30-02.3"),
        (2, 2, "Pieces", "medium", "elevee", "open", "L'unite de la graisse dielectrique n'est pas harmonisee avec le catalogue.", "Utiliser l'unite du catalogue.", "Pieces / PN-DEMO-2402"),
        # Analyse 3 : corpus quasi conforme (2 anomalies)
        (1, 3, "Securite", "medium", "moyenne", "open", "La mise en garde avant essai est presente mais sans niveau de criticite.", "Preciser le niveau de criticite.", "Taches / 21-30-02.3"),
        (2, 3, "Outillage", "low", "faible", "open", "La prochaine calibration de TL-3001 arrive a echeance proche.", "Verifier la date de calibration.", "Outillage / TL-3001"),
    ]


def _seed_analysis(db: Session, project: Project) -> None:
    """Runs d'analyse et anomalies synthetiques : alimentent le dashboard demo."""
    now = datetime.now(timezone.utc)
    runs = []
    for age in _RUN_AGES:
        started = now - timedelta(days=age)
        run = AnalysisRun(
            project_id=project.id,
            started_at=started,
            finished_at=started + timedelta(minutes=2),
            status="completed",
            summary="{}",
        )
        db.add(run)
        runs.append(run)
    db.flush()

    versions = [
        db.scalar(
            select(FileVersion)
            .join(File, FileVersion.file_id == File.id)
            .where(File.project_id == project.id, FileVersion.filename == spec[0])
            .order_by(FileVersion.uploaded_at.desc())
        )
        for spec in _SHEETS
    ]
    for file_idx, run_idx, category, severity, confidence, status, message, suggestion, location in _anomaly_specs():
        version = versions[file_idx]
        if version is None:
            continue
        created = now - timedelta(days=_RUN_AGES[run_idx])
        db.add(
            Anomaly(
                project_id=project.id,
                file_version_id=version.id,
                run_id=runs[run_idx].id,
                type="personnalisee",
                category=category,
                severity=severity,
                confidence=confidence,
                message=message,
                suggestion=suggestion,
                location=location,
                status=status,
                feedback=_REJECTION_MOTIFS.get((file_idx, run_idx, category)) if status == "rejected" else None,
                created_at=created,
                resolved_at=created + timedelta(days=2) if status == "fixed" else None,
            )
        )


def seed_demo_project(db: Session) -> Project:
    """Cree le projet demo s'il n'existe pas ; sinon le renvoie tel quel."""
    from app.api.files import _ingest_file

    existing = db.scalar(select(Project).where(Project.name == DEMO_PROJECT_NAME))
    if existing is not None:
        run_count = db.scalar(select(func.count()).select_from(AnalysisRun).where(AnalysisRun.project_id == existing.id))
        rejected_without_motif = db.scalar(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.project_id == existing.id,
                Anomaly.status == "rejected",
                (Anomaly.feedback.is_(None)) | (Anomaly.feedback == ""),
            )
        )
        misattached = db.scalar(
            select(func.count())
            .select_from(Anomaly)
            .join(FileVersion, Anomaly.file_version_id == FileVersion.id)
            .join(File, FileVersion.file_id == File.id)
            .where(Anomaly.project_id == existing.id, File.project_id != existing.id)
        )
        if run_count == len(_RUN_AGES) and not rejected_without_motif and not misattached:
            return existing
        # Jeu de donnees demo obsolete : on le regenere
        remove_demo_project(db)

    project = Project(name=DEMO_PROJECT_NAME, description=DEMO_PROJECT_DESCRIPTION)
    db.add(project)
    db.flush()
    for spec in _SHEETS:
        _ingest_file(db, project, _build_workbook(spec), spec[0], _XLSX_MIME)
    db.flush()
    _seed_analysis(db, project)
    db.commit()
    db.refresh(project)
    return project


def remove_demo_project(db: Session) -> None:
    project = db.scalar(select(Project).where(Project.name == DEMO_PROJECT_NAME))
    if project is None:
        return
    project_dir = Path(settings.storage_dir) / f"project_{project.id}"
    db.delete(project)
    db.commit()
    shutil.rmtree(project_dir, ignore_errors=True)
