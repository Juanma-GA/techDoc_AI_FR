"""Check « Général » — texte et structure des opérations.

Types d'anomalies émis :
- `texte`         : espace en début de phrase, point manquant en fin
                    d'opération, début de phrase non conforme (doit commencer
                    par un verbe d'action, « Si … alors », ou « Note »).
- `ordre_taches`  : colonne « Ordre des tâches » avec cellule vide, saut de
                    numéro ou doublon.
- `tache_induite` : tâche appelée sans référence en colonne « Tâche induite ».
- `orthographe`   : fautes d'orthographe / grammaire / traduction — jugé par
                    Mistral (skippé si Mistral non configuré).
"""

from __future__ import annotations

import re
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.checks.ftm_doc import find_column, find_sheet, latest_version, make_anomaly, parse_sheets
from app.core.mistral_client import MistralClient
from app.core.rules import load_rules
from app.core.rules_catalog import (
    TEXTE_FORMAT_PHRASE, TEXTE_ORDRE_TACHES, TEXTE_ORTHOGRAPHE,
    TEXTE_REMPLACER_DEPOSE_POSE, TEXTE_TACHE_INDUITE,
)
from app.core.rules_registry import resolve_rules
from app.db.models import Anomaly, FileVersion, Project

# Mots non-verbes qui, en tête de phrase, trahissent un début non conforme.
_NON_VERBE_DEBUT = {
    "le", "la", "les", "un", "une", "des", "du", "il", "elle", "on",
    "ce", "cette", "ces", "au", "aux", "pour", "dans", "sur", "avec", "cet",
}
_MAX_PAR_TYPE = 40  # anti-bruit : plafonne le nombre d'anomalies par type
_APPEL_TACHE_RE = re.compile(r"DMC[-A-Z0-9]{4,}|t[âa]che\s+n[°o]?\s*\d", re.IGNORECASE)


def _is_operation(cell: str) -> bool:
    """Heuristique : la cellule ressemble à une opération rédigée (phrase)."""
    s = cell.strip()
    return len(s) >= 12 and " " in s and any(c.islower() for c in s)


def run_text_rules(
    db: Session,
    project: Project,
    run_id: uuid.UUID,
    mistral: Optional[MistralClient] = None,
) -> list[Anomaly]:
    resolved = resolve_rules()
    r_phrase = resolved[TEXTE_FORMAT_PHRASE.id]
    r_ordre = resolved[TEXTE_ORDRE_TACHES.id]
    r_induite = resolved[TEXTE_TACHE_INDUITE.id]
    r_remplacer = resolved[TEXTE_REMPLACER_DEPOSE_POSE.id]
    r_ortho = resolved[TEXTE_ORTHOGRAPHE.id]
    col_ordre = str(r_ordre.params["colonne"])
    col_induite = str(r_induite.params["colonne"])
    debuts_autorises = r_phrase.params.get("debuts_autorises") or [
        "verbe_action", "si_alors", "note",
    ]
    check_espace = bool(r_phrase.params.get("pas_espace_debut", True))
    check_point = bool(r_phrase.params.get("point_fin_operation", True))

    anomalies: list[Anomaly] = []
    counts: dict[str, int] = {}

    def _add(atype: str, latest: FileVersion, severity: str, msg: str,
             sug: str = "", loc: str = "", confidence: str = "elevee") -> None:
        if counts.get(atype, 0) >= _MAX_PAR_TYPE:
            return
        a = make_anomaly(project, latest, run_id, atype, severity, msg, sug, loc, confidence)
        db.add(a)
        anomalies.append(a)
        counts[atype] = counts.get(atype, 0) + 1

    for f in project.files:
        latest = latest_version(f)
        if latest is None:
            continue
        sheets = parse_sheets(latest.extracted_text or "")
        title, rows = find_sheet(sheets, "tâche de maintenance", "tache de maintenance",
                                 "maintenance", "opération", "operation")
        if not rows:
            # Onglet métier non identifié : on retombe sur toutes les lignes.
            rows = [r for rs in sheets.values() for r in rs]
            title = "Document"

        # --- texte : espace de tête, point final, début de phrase ----------
        op_cells: list[str] = []
        for row in rows:
            for cell in row:
                if not _is_operation(cell):
                    continue
                s = cell.strip()
                op_cells.append(s)

                if r_phrase.enabled:
                    if check_espace and cell != cell.lstrip():
                        _add("texte", latest, "medium",
                             "Espace en début de phrase.",
                             "Supprimer le ou les espaces en tête de cellule : un espace "
                             "de tête casse la conversion XML du livrable.",
                             loc=f"{title} — {s[:80]}")

                    if check_point and not s.endswith("."):
                        _add("texte", latest, "medium",
                             "Opération non terminée par un point.",
                             "Clore chaque fin d'opération par un point : son absence "
                             "casse la conversion XML du livrable.",
                             loc=f"{title} — {s[:80]}")

                    first = re.split(r"[\s’']", s, maxsplit=1)[0].strip(".,;:").lower()
                    if "verbe_action" in debuts_autorises and first in _NON_VERBE_DEBUT:
                        _add("texte", latest, "medium",
                             f"Début de phrase non conforme : « {s[:40]}… ».",
                             "Une phrase doit commencer par un verbe d'action, "
                             "par « Si … alors », ou par « Note ».",
                             loc=f"{title} — {s[:80]}")
                    elif first == "si" and "si_alors" in debuts_autorises and "alors" not in s.lower():
                        _add("texte", latest, "medium",
                             "Phrase en « Si » sans « alors ».",
                             "Une condition « Si » doit être suivie de « alors ».",
                             loc=f"{title} — {s[:80]}")

        # --- ordre_taches : cellule vide / saut / doublon ------------------
        col = find_column(rows, "ordre des tâches", "ordre des taches", "ordre") if r_ordre.enabled else -1
        if col >= 0:
            header_row = next(
                (i for i, r in enumerate(rows[:8])
                 if col < len(r) and "ordre" in r[col].lower()),
                0,
            )
            seq: list[int] = []
            seen: set[int] = set()
            for r in rows[header_row + 1:]:
                cell = r[col].strip() if col < len(r) else ""
                if not cell:
                    _add("ordre_taches", latest, "high",
                         "Cellule vide dans la colonne « Ordre des tâches ».",
                         "Renseigner un numéro d'ordre pour chaque tâche.",
                         loc=title)
                    continue
                try:
                    n = int(float(cell.replace(",", ".")))
                except ValueError:
                    continue
                if n in seen:
                    _add("ordre_taches", latest, "high",
                         f"Numéro d'ordre en doublon : {n}.",
                         "Chaque numéro d'ordre doit être unique.",
                         loc=title)
                seen.add(n)
                seq.append(n)
            if seq:
                ordered = sorted(seen)
                for prev, nxt in zip(ordered, ordered[1:]):
                    if nxt - prev > 1:
                        _add("ordre_taches", latest, "medium",
                             f"Saut de numéro dans l'ordre des tâches : {prev} → {nxt}.",
                             "La numérotation des tâches doit être continue.",
                             loc=title)

        # --- remplacer → 3.1 déposer + 3.2 poser --------------------------
        # Si le livrable est une procédure de remplacement, l'ordre des tâches
        # doit comporter au moins une ligne 3.1 (dépose) et une ligne 3.2 (pose).
        if r_remplacer.enabled:
            full_text_lower = (latest.extracted_text or "").lower()
            if "remplacer" in full_text_lower or "remplacement" in full_text_lower:
                # Recherche les lignes 3.1 et 3.2 dans n'importe quelle cellule.
                has_3_1 = False
                has_3_1_depose = False
                has_3_2 = False
                has_3_2_pose = False
                for row in rows:
                    joined = " ".join(row).lower()
                    # Match 3.1 en début de cellule OU "ordre 3.1" / "tâche 3.1"
                    if re.search(r"(?:^|[\s|])3\.1(?:[\s.|]|$)", " | ".join(row)):
                        has_3_1 = True
                        if "depose" in joined or "déposer" in joined or "déposé" in joined:
                            has_3_1_depose = True
                    if re.search(r"(?:^|[\s|])3\.2(?:[\s.|]|$)", " | ".join(row)):
                        has_3_2 = True
                        if "poser" in joined or "posé" in joined or "pose" in joined:
                            has_3_2_pose = True
                if not (has_3_1 and has_3_1_depose):
                    _add("ordre_taches", latest, "high",
                         "Procédure de remplacement sans ligne 3.1 « déposer ».",
                         "Une procédure de remplacement doit contenir une ligne 3.1 avec une opération de dépose.",
                         loc=title)
                if not (has_3_2 and has_3_2_pose):
                    _add("ordre_taches", latest, "high",
                         "Procédure de remplacement sans ligne 3.2 « poser ».",
                         "Une procédure de remplacement doit contenir une ligne 3.2 avec une opération de pose.",
                         loc=title)

        # --- tache_induite : tâche appelée sans référence ------------------
        col_ind = find_column(rows, "tâche induite", "tache induite", "induite") if r_induite.enabled else -1
        if col_ind >= 0:
            for r in rows:
                joined = " ".join(r)
                if not _APPEL_TACHE_RE.search(joined):
                    continue
                induced = r[col_ind].strip() if col_ind < len(r) else ""
                if not induced:
                    _add("tache_induite", latest, "high",
                         "Tâche appelée sans référence en colonne « Tâche induite ».",
                         f"Reporter la référence de la tâche appelée dans « {col_induite} ».",
                         loc=f"{title} — {joined[:80]}")

        # --- orthographe : passe Mistral (optionnelle) ---------------------
        if r_ortho.enabled and mistral is not None and op_cells:
            for item in _llm_orthographe(mistral, op_cells[:60]):
                _add("orthographe", latest, "low",
                     item.get("message", "Faute détectée"),
                     item.get("correction", ""),
                     loc=(item.get("extrait", "") or "")[:120],
                     confidence="moyenne")

    return anomalies


def _llm_orthographe(mistral: MistralClient, cells: list[str]) -> list[dict]:
    """Demande à Mistral de relever fautes d'orthographe / grammaire /
    traduction sur un échantillon d'opérations. Renvoie [] en cas d'erreur."""
    custom = (load_rules().get("instructions_libres") or "").strip()
    system = (
        "Tu es relecteur de fiches de tâches de maintenance en français. "
        "On te donne une liste numérotée d'opérations. Relève uniquement les "
        "fautes d'orthographe, de grammaire et de traduction (anglicismes, "
        "termes non traduits). N'invente rien. "
        + (f"Consignes complémentaires : {custom}. " if custom else "")
        + 'Réponds STRICTEMENT en JSON : '
        '{"fautes": [{"extrait": "phrase fautive", "message": "nature de la faute", '
        '"correction": "phrase corrigée"}]}.'
    )
    user = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(cells))
    try:
        result = mistral.chat_json([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ])
        fautes = result.get("fautes", []) if isinstance(result, dict) else []
        return [x for x in fautes if isinstance(x, dict)]
    except Exception:  # noqa: BLE001
        return []
