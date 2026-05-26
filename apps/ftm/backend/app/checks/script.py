"""Check « Script » — type d'anomalie : `script`.

Le script de la FTM doit :
- commencer par le préfixe normalisé `DMC-TG5-` suivi d'un code (AAAA) ;
- être identique au script de référence du suivi ATM FTM (colonne BF du
  classeur référentiel), lorsqu'un référentiel est attaché au projet.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.checks.ftm_doc import latest_version, make_anomaly
from app.core.mistral_client import MistralClient
from app.core.rules import reference_column
from app.core.rules_catalog import SCRIPT_FORMAT
from app.core.rules_registry import resolve_rules
from app.db.models import Anomaly, Project
from app.parsers.reference import reference_column_values

# Premier jeton de forme DMC-… rencontré dans le livrable = script de la FTM.
SCRIPT_RE = re.compile(r"DMC[-A-Z0-9]+", re.IGNORECASE)


def run_script(
    db: Session,
    project: Project,
    run_id: uuid.UUID,
    mistral: Optional[MistralClient] = None,
) -> list[Anomaly]:
    resolved = resolve_rules()[SCRIPT_FORMAT.id]
    anomalies: list[Anomaly] = []
    if not resolved.enabled:
        return anomalies  # règle désactivée → aucune anomalie
    prefix = str(resolved.params["prefix"])
    try:
        fmt = re.compile(str(resolved.params["regex"]))
    except re.error:
        fmt = re.compile(r"^DMC-TG5-")
    atm_col = str(resolved.params["atm_colonne"])
    # Colonne du script dans le suivi ATM : onglet + colonne issus du registre
    # de reference du projet ; onglet vide => recherche par mots-cles (compat).
    col = reference_column(project, "script") or {}
    atm_scripts = {
        s.upper()
        for s in reference_column_values(
            project.reference_path,
            col.get("sheet", ""),
            col.get("column") or atm_col,
            ("atm", "suivi"),
        )
    }

    def _add(a: Anomaly) -> None:
        db.add(a)
        anomalies.append(a)

    for f in project.files:
        latest = latest_version(f)
        if latest is None:
            continue
        text = latest.extracted_text or ""
        m = SCRIPT_RE.search(text)
        script = m.group(0).upper() if m else ""

        if not script:
            _add(make_anomaly(
                project, latest, run_id, "script", "high",
                "Aucun script détecté dans le livrable FTM.",
                f"Le script doit figurer dans la FTM et commencer par « {prefix} ».",
            ))
            continue

        if not fmt.match(script):
            _add(make_anomaly(
                project, latest, run_id, "script", "high",
                f"Script « {script} » non conforme au format attendu.",
                f"Le script doit commencer par « {prefix} » suivi de 4 caracteres (AAAA).",
                location=f"Script : {script}",
            ))

        # Cross-check référentiel : le script doit exister en colonne BF du
        # suivi ATM. Skippé silencieusement si aucun référentiel n'est attaché.
        if atm_scripts and script not in atm_scripts:
            _add(make_anomaly(
                project, latest, run_id, "script", "high",
                f"Script « {script} » introuvable dans le suivi ATM FTM (colonne {atm_col}).",
                "Aligner le script de la FTM sur celui du suivi ATM FTM du référentiel.",
                location=f"Script : {script}",
            ))

    return anomalies
