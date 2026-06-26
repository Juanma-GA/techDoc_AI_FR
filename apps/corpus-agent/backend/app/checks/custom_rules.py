"""Check « Règles personnalisées (IA) » — type d'anomalie : `personnalisee`.

L'utilisateur définit ses propres règles en langage naturel dans l'onglet
Paramètres (`regles_personnalisees` : id / label / consigne / severity).
À chaque analyse, le Mistral embarqué évalue le livrable FTM contre chacune
de ces règles et renvoie les écarts.

Skippé silencieusement si Mistral n'est pas configuré ou si aucune règle
personnalisée n'est définie.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.checks.ftm_doc import latest_version, make_anomaly
from app.core.mistral_client import MistralClient
from app.core.rules import load_rules, reference_column
from app.db.models import Anomaly, Project
from app.parsers.reference import reference_column_values

_SEVERITY = {
    "faible": "low", "moyenne": "medium", "haute": "high",
    "low": "low", "medium": "medium", "high": "high",
}
# Niveau de confiance renvoyé par Mistral → slug interne.
_CONFIDENCE = {
    "faible": "faible", "moyenne": "moyenne", "elevee": "elevee",
    "élevée": "elevee", "haute": "elevee", "low": "faible",
    "medium": "moyenne", "high": "elevee",
}
_MAX_TEXT = 15000  # cap d'envoi à Mistral (caractères)


def _normalize_for_verify(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _is_extract_grounded(extrait: str, text: str) -> bool:
    """Garde-fou anti-hallucination : l'extrait Mistral doit apparaître
    littéralement (après normalisation casse + espaces) dans la FTM. Sinon
    l'écart est suspect — on conserve l'anomalie mais on dégrade la confiance."""
    if not extrait:
        return False
    return _normalize_for_verify(extrait) in _normalize_for_verify(text)


def _load_custom_rules() -> list[dict]:
    """Règles personnalisées valides (consigne non vide), normalisées."""
    out: list[dict] = []
    for r in (load_rules().get("regles_personnalisees") or []):
        if not isinstance(r, dict):
            continue
        consigne = str(r.get("consigne") or "").strip()
        if not consigne:
            continue
        out.append({
            "id": str(r.get("id") or f"r{len(out) + 1}"),
            "label": str(r.get("label") or "Règle personnalisée"),
            "consigne": consigne,
            "severity": _SEVERITY.get(str(r.get("severity") or "medium").lower(), "medium"),
        })
    return out


# Placeholder de colonne de reference : {nom} ou nom est un identifiant valide.
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z][a-zA-Z0-9_]*)\}")
_MAX_PLACEHOLDER_VALUES = 200


def _resolve_placeholders(consigne: str, project: Project) -> str:
    """Remplace chaque `{nom}` de la consigne par les valeurs de la colonne de
    reference homonyme du projet. Un `{nom}` sans colonne correspondante est
    laisse tel quel (l'IA le verra comme du texte)."""
    def _sub(match: "re.Match[str]") -> str:
        name = match.group(1)
        col = reference_column(project, name)
        if col is None:
            return match.group(0)
        values = reference_column_values(
            project.reference_path, col.get("sheet", ""), col.get("column", ""),
        )
        if not values:
            return f"[colonne de reference « {name} » : aucune valeur]"
        shown = values[:_MAX_PLACEHOLDER_VALUES]
        extra = len(values) - len(shown)
        suffix = f" (+{extra} autres)" if extra > 0 else ""
        return f"[colonne de reference « {name} » : {', '.join(shown)}{suffix}]"

    return _PLACEHOLDER_RE.sub(_sub, consigne)


def run_custom_rules(
    db: Session,
    project: Project,
    run_id: uuid.UUID,
    mistral: Optional[MistralClient] = None,
) -> list[Anomaly]:
    rules = _load_custom_rules()
    anomalies: list[Anomaly] = []
    if mistral is None or not rules:
        return anomalies

    # Resout les placeholders {nom} de colonne de reference dans chaque consigne.
    rules = [
        {**r, "consigne": _resolve_placeholders(r["consigne"], project)}
        for r in rules
    ]
    by_id = {r["id"]: r for r in rules}

    for f in project.files:
        latest = latest_version(f)
        if latest is None:
            continue
        text = (latest.extracted_text or "").strip()
        if not text:
            continue
        for item in _llm_eval(mistral, text, rules):
            rule = by_id.get(str(item.get("regle_id") or ""))
            severity = rule["severity"] if rule else _SEVERITY.get(
                str(item.get("severity") or "medium").lower(), "medium"
            )
            label = rule["label"] if rule else "Règle personnalisée"
            message = (item.get("message") or "").strip() or f"Écart sur « {label} »"
            extrait = (item.get("extrait") or "").strip()
            confidence = _CONFIDENCE.get(
                str(item.get("confiance") or "moyenne").lower(), "moyenne"
            )
            if not _is_extract_grounded(extrait, text):
                confidence = "faible"
                message = f"[non vérifié] {message}"
            a = make_anomaly(
                project, latest, run_id, "personnalisee", severity,
                f"[{label}] {message}",
                (item.get("suggestion") or "").strip(),
                extrait[:200],
                confidence=confidence,
            )
            db.add(a)
            anomalies.append(a)

    return anomalies


def _llm_eval(mistral: MistralClient, text: str, rules: list[dict]) -> list[dict]:
    """Soumet les règles personnalisées + le contenu FTM à Mistral.
    Renvoie la liste d'écarts (dicts), `[]` en cas d'erreur."""
    excerpt = text if len(text) <= _MAX_TEXT else text[:_MAX_TEXT] + "\n[...document tronqué...]"
    general = (load_rules().get("instructions_libres") or "").strip()
    rules_json = json.dumps(
        [{"id": r["id"], "label": r["label"], "consigne": r["consigne"]} for r in rules],
        ensure_ascii=False,
    )
    system = (
        "Tu es un relecteur expert de documents techniques en "
        "français. On te fournit une liste de RÈGLES PERSONNALISÉES (JSON — le "
        "champ « consigne » est la règle exprimée en langage naturel) et le "
        "CONTENU d'un document. Pour CHAQUE règle, repère dans le document les écarts à "
        "cette règle. Ne signale que des écarts réels et vérifiables, n'invente "
        "rien. "
        + (f"Consignes générales : {general}. " if general else "")
        + 'Règle absolue sur le champ « extrait » : il DOIT être une COPIE '
        'VERBATIM (caractère pour caractère, sans paraphrase, sans correction, '
        'sans inversion de sens) d\'un passage présent dans le CONTENU DU '
        'DOCUMENT ci-dessous. Si tu ne peux pas citer verbatim le passage qui '
        'enfreint la règle, NE SIGNALE PAS l\'écart. Ne déduis pas une phrase '
        'qui « devrait » être là : si elle n\'est pas écrite dans le document, elle '
        'n\'existe pas. Exemple à NE PAS faire : signaler que « Dépréparer la '
        'rame » est appelée alors que le document contient « Préparer la rame » — '
        'ce sont deux phrases distinctes, ne les confonds pas. '
        + 'Réponds STRICTEMENT en JSON, en français : '
        '{"anomalies": [{"regle_id": "id de la règle concernée", '
        '"message": "écart constaté", "suggestion": "correction proposée", '
        '"extrait": "copie verbatim du passage fautif du document", '
        '"confiance": "faible|moyenne|elevee"}]}. '
        'Le champ « confiance » indique ta certitude sur cet écart : elevee si '
        'la règle est clairement enfreinte, faible si c\'est ambigu. '
        'Si aucune règle n\'est enfreinte, retourne {"anomalies": []}.'
    )
    user = f"RÈGLES PERSONNALISÉES :\n{rules_json}\n\nCONTENU DU DOCUMENT :\n{excerpt}"
    try:
        result = mistral.chat_json([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ])
        items = result.get("anomalies", []) if isinstance(result, dict) else []
        return [x for x in items if isinstance(x, dict)]
    except Exception:  # noqa: BLE001
        return []
