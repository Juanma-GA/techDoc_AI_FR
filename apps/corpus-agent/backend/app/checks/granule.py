"""Check « Granule » — type d'anomalie : `granule`.

La (les) granule(s) de la FTM se reportent depuis le suivi ATM FTM :
- opération hors dépose-pose : 1 granule, colonne BH ;
- opération de dépose-pose : 2 granules — la dépose (ligne 3.1) prend la
  colonne BH, la pose (ligne 3.2) prend la colonne BJ.

Le rapprochement FTM ↔ ligne ATM se fait via le script (colonne BF).
Skippé silencieusement si aucun référentiel n'est attaché au projet.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.checks.ftm_doc import latest_version, make_anomaly
from app.checks.script import SCRIPT_RE
from app.core.mistral_client import MistralClient
from app.core.rules import reference_columns_for
from app.core.rules_catalog import GRANULE_REPORT
from app.core.rules_registry import resolve_rules
from app.db.models import Anomaly, Project
from app.parsers.reference import rows_with_letters, rows_with_letters_for_sheet


def run_granule(
    db: Session,
    project: Project,
    run_id: uuid.UUID,
    mistral: Optional[MistralClient] = None,
) -> list[Anomaly]:
    resolved = resolve_rules()[GRANULE_REPORT.id]
    anomalies: list[Anomaly] = []
    if not resolved.enabled:
        return anomalies
    # Colonnes du suivi ATM issues du registre de reference du projet. Les 3
    # builtin partagent un onglet (validite garantie a l'enregistrement du
    # mapping) ; onglet vide => recherche par mots-cles (compat).
    cols = {c["name"]: c for c in reference_columns_for(project)}
    sc = cols.get("script", {})
    gd = cols.get("granule_defaut", {})
    gp = cols.get("granule_pose", {})
    bf = sc.get("column") or "BF"
    col_def = gd.get("column") or str(resolved.params["atm_colonne_defaut"])
    col_pose = gp.get("column") or str(resolved.params["atm_colonne_pose"])
    atm_sheet = gd.get("sheet") or sc.get("sheet") or ""

    if atm_sheet:
        atm_rows = rows_with_letters_for_sheet(
            project.reference_path, atm_sheet, (bf, col_def, col_pose)
        )
    else:
        atm_rows = rows_with_letters(
            project.reference_path, ("atm", "suivi"), (bf, col_def, col_pose)
        )

    if not atm_rows:
        return anomalies  # pas de référentiel → check inactif

    def _add(a: Anomaly) -> None:
        db.add(a)
        anomalies.append(a)

    for f in project.files:
        latest = latest_version(f)
        if latest is None:
            continue
        text = latest.extracted_text or ""
        low = text.lower()

        m = SCRIPT_RE.search(text)
        script = m.group(0).upper() if m else ""
        row = next((r for r in atm_rows if r.get(bf, "").upper() == script), None)
        if row is None:
            # Script non rapproché : déjà signalé par le check `script`.
            continue

        # Opération de dépose-pose si la FTM mentionne dépose ET pose.
        depose_pose = (
            ("dépose" in low or "depose" in low) and "pose" in low
        )

        expected: list[tuple[str, str, str]] = []
        g_def = row.get(col_def, "").strip()
        g_pose = row.get(col_pose, "").strip()
        if g_def:
            role = "retrait (ligne 3.1)" if depose_pose else "opération"
            expected.append((g_def, role, col_def))
        if depose_pose and g_pose:
            expected.append((g_pose, "remise (ligne 3.2)", col_pose))

        for granule, role, col in expected:
            if granule not in text:
                _add(make_anomaly(
                    project, latest, run_id, "granule", "high",
                    f"Élément attendu « {granule} » ({role}) absent du document.",
                    f"Reporter dans le document l'élément de la colonne {col} du référentiel.",
                    location=f"Élément — {role}",
                ))

    return anomalies
