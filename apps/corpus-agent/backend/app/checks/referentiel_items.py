"""Check « Référentiel » — rechanges, outillages, infrastructure, en-tête.

Types d'anomalies émis :
- `rechange`       : doublon, plusieurs rechanges sur une ligne, rechange du
                     Récapitulatif absent de la Tâche de maintenance, nom non
                     conforme au LCC / à la BASL.
- `outillage`      : outillage du Récapitulatif absent de la Tâche de
                     maintenance, désignation non conforme à la BASL.
- `infrastructure` : infrastructure citée hors du Récapitulatif.
- `entete`         : champ d'en-tête du Récapitulatif absent.

Les contrôles structurels (doublon, présence croisée) tournent sans
référentiel. Les cross-checks de désignation BASL/LCC ne tournent que si un
classeur référentiel est attaché — sinon ils sont skippés silencieusement.

NB : ces contrôles sont heuristiques (localisation des colonnes par mot-clé
d'en-tête) et à calibrer sur le gabarit FTM réel.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.checks.ftm_doc import find_column, find_sheet, latest_version, make_anomaly, parse_sheets
from app.core.mistral_client import MistralClient
from app.core.rules import basl_column
from app.core.rules_catalog import (
    ENTETE_RECAP_CHAMPS, INFRASTRUCTURE_BASL,
    OUTILLAGES_RECAP_PRESENT, OUTILLAGES_SPECIFIQUE, OUTILLAGES_STANDARD,
    RECHANGES_DOUBLONS, RECHANGES_NOM_BASL, RECHANGES_RECAP_PRESENT,
)
from app.core.rules_registry import resolve_rules
from app.db.models import Anomaly, FileVersion, Project
from app.parsers.reference import reference_column_values, sheet_names, sheet_rows

_MULTI_ITEM_RE = re.compile(r";|\s\+\s|\s/\s")


def _collect_column(rows: list[list[str]], *header_kw: str) -> list[str]:
    """Valeurs non vides de la colonne dont l'en-tête matche un mot-clé."""
    col = find_column(rows, *header_kw)
    if col < 0:
        return []
    kws = [k.lower() for k in header_kw]
    header_row = next(
        (i for i, r in enumerate(rows[:8])
         if col < len(r) and any(k in r[col].lower() for k in kws)),
        0,
    )
    out: list[str] = []
    for r in rows[header_row + 1:]:
        v = r[col].strip() if col < len(r) else ""
        if v:
            out.append(v)
    return out


def _ref_cells(path: Optional[str]) -> set[str]:
    """Ensemble des valeurs de cellule de toutes les feuilles du fichier BASL,
    pour tester l'appartenance d'un nom de rechange / d'une désignation."""
    cells: set[str] = set()
    for name in sheet_names(path):
        for row in sheet_rows(path, name):
            for c in row:
                c = c.strip()
                if c:
                    cells.add(c.casefold())
    return cells


def run_referentiel_items(
    db: Session,
    project: Project,
    run_id: uuid.UUID,
    mistral: Optional[MistralClient] = None,
) -> list[Anomaly]:
    resolved = resolve_rules()
    r_rech_basl = resolved[RECHANGES_NOM_BASL.id]
    r_rech_doublons = resolved[RECHANGES_DOUBLONS.id]
    r_rech_recap = resolved[RECHANGES_RECAP_PRESENT.id]
    r_out_std = resolved[OUTILLAGES_STANDARD.id]  # noqa: F841 — réservé phase ultérieure (check pose/dépose)
    r_out_spec = resolved[OUTILLAGES_SPECIFIQUE.id]  # noqa: F841
    r_out_recap = resolved[OUTILLAGES_RECAP_PRESENT.id]
    r_infra = resolved[INFRASTRUCTURE_BASL.id]
    r_entete = resolved[ENTETE_RECAP_CHAMPS.id]
    exceptions = {e.casefold() for e in (r_out_recap.params.get("exceptions") or [])}

    anomalies: list[Anomaly] = []

    def _add(latest: FileVersion, atype: str, severity: str, msg: str,
             sug: str = "", loc: str = "") -> None:
        a = make_anomaly(project, latest, run_id, atype, severity, msg, sug, loc)
        db.add(a)
        anomalies.append(a)

    # Cross-checks BASL : nom des rechanges, désignations outillage/infra,
    # champs d'en-tête. Chaque champ teste l'appartenance à SA colonne BASL
    # mappée (registre `basl_columns`) ; si la colonne builtin n'est pas mappée
    # (onglet/colonne vide), on retombe sur l'union de toutes les cellules de la
    # BASL (comportement historique). Le LCC est couvert par le même fichier.
    _all_basl_cells: Optional[set[str]] = None

    def _basl_set(field: str) -> set[str]:
        nonlocal _all_basl_cells
        col = basl_column(project, field) or {}
        if col.get("sheet") and col.get("column"):
            return {
                v.casefold()
                for v in reference_column_values(
                    project.basl_path, col["sheet"], col["column"]
                )
            }
        if _all_basl_cells is None:
            _all_basl_cells = _ref_cells(project.basl_path)
        return _all_basl_cells

    rech_ref = _basl_set("rechange")
    out_ref = _basl_set("outillage")
    infra_ref = _basl_set("infrastructure")

    for f in project.files:
        latest = latest_version(f)
        if latest is None:
            continue
        sheets = parse_sheets(latest.extracted_text or "")
        _, recap = find_sheet(sheets, "récapitulatif", "recapitulatif", "récap", "recap")
        _, tache = find_sheet(sheets, "tâche de maintenance", "tache de maintenance", "maintenance")
        tache_text = "\n".join(" | ".join(r) for r in tache).casefold()

        # --- rechanges -----------------------------------------------------
        seen: set[str] = set()
        for v in _collect_column(recap, "rechange"):
            key = v.casefold()
            if r_rech_doublons.enabled and _MULTI_ITEM_RE.search(v) \
                    and r_rech_doublons.params.get("un_par_ligne", True):
                _add(latest, "rechange", "medium",
                     f"Plusieurs rechanges sur une même ligne : « {v} ».",
                     "Une ligne ne doit contenir qu'un seul rechange.",
                     loc="Récapitulatif")
            if r_rech_doublons.enabled and key in seen:
                _add(latest, "rechange", "medium",
                     f"Rechange en doublon : « {v} ».",
                     "Supprimer la ligne de rechange dupliquée.",
                     loc="Récapitulatif")
            seen.add(key)
            if r_rech_recap.enabled and tache and key not in tache_text:
                _add(latest, "rechange", "high",
                     f"Rechange « {v} » présent au Récapitulatif mais absent de la Tâche de maintenance.",
                     "Reporter le rechange dans l'onglet Tâche de maintenance.",
                     loc="Récapitulatif")
            if r_rech_basl.enabled and rech_ref and key not in rech_ref:
                _add(latest, "rechange", "medium",
                     f"Nom de rechange « {v} » non retrouvé dans le LCC / la BASL.",
                     "Reprendre exactement le libellé du rechange depuis le LCC / la BASL.",
                     loc="Récapitulatif")

        # --- outillages ----------------------------------------------------
        if r_out_recap.enabled:
            for v in _collect_column(recap, "outillage", "outil"):
                key = v.casefold()
                if key in exceptions:
                    continue
                if tache and key not in tache_text:
                    _add(latest, "outillage", "high",
                         f"Outillage « {v} » présent au Récapitulatif mais absent de la Tâche de maintenance.",
                         "Reporter l'outillage dans l'onglet Tâche de maintenance.",
                         loc="Récapitulatif")
                if out_ref and key not in out_ref:
                    _add(latest, "outillage", "medium",
                         f"Désignation d'outillage « {v} » non retrouvée dans la BASL.",
                         "Reprendre la désignation de l'outillage depuis la BASL.",
                         loc="Récapitulatif")

        # --- infrastructure : citée uniquement sur le Récapitulatif --------
        if r_infra.enabled:
            seulement_recap = bool(r_infra.params.get("seulement_recap", True))
            for v in _collect_column(recap, "infrastructure", "infra"):
                if seulement_recap and tache and v.casefold() in tache_text:
                    _add(latest, "infrastructure", "medium",
                         f"Infrastructure « {v} » citée hors du Récapitulatif.",
                         "Les infrastructures ne sont citées que sur le Récapitulatif.",
                         loc="Tâche de maintenance")
                if infra_ref and v.casefold() not in infra_ref:
                    _add(latest, "infrastructure", "medium",
                         f"Infrastructure « {v} » non retrouvée dans la BASL.",
                         "Reprendre référence et désignation de l'infrastructure depuis la BASL.",
                         loc="Récapitulatif")

        # --- en-tête du Récapitulatif --------------------------------------
        if r_entete.enabled:
            recap_text = "\n".join(" | ".join(r) for r in recap).casefold()
            for champ in (r_entete.params.get("champs_identiques_basl") or []):
                if recap and champ.casefold() not in recap_text:
                    _add(latest, "entete", "medium",
                         f"Champ d'en-tête « {champ} » absent du Récapitulatif.",
                         f"Renseigner « {champ} » à l'identique de la BASL.",
                         loc="Récapitulatif (en-tête)")

    return anomalies
