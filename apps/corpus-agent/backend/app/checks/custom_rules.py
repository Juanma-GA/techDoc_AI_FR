"""Check « Règles personnalisées (IA) » — type d'anomalie : `personnalisee`.

L'utilisateur définit ses propres règles en langage naturel dans l'onglet
Paramètres (`regles_personnalisees` : id / label / consigne / severity).
À chaque analyse, le Mistral embarqué évalue le livrable FTM contre chacune
de ces règles et renvoie les écarts.

Skippé silencieusement si Mistral n'est pas configuré ou si aucune règle
personnalisée n'est définie.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field

import structlog
from sqlalchemy.orm import Session

from app.checks.ftm_doc import latest_version, make_anomaly
from app.core.mistral_client import MistralClient
from app.core.prompt_sanitizer import sanitize_document
from app.core.rules import basl_column, load_rules, reference_column
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
CUSTOM_RULE_PROMPT_VERSION = "custom-rules-v1"
log = structlog.get_logger(__name__)


@dataclass
class RuleEvaluationStats:
    active_rules: int = 0
    evaluation_calls: int = 0
    evaluation_failures: int = 0
    files_evaluated: int = 0
    rules_evaluated: int = 0
    evaluated_file_ids: set[uuid.UUID] = field(default_factory=set)
    rule_set_sha256: str = ""


def _normalize_for_verify(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _is_extract_grounded(extrait: str, text: str) -> bool:
    """Garde-fou anti-hallucination : l'extrait Mistral doit apparaître
    littéralement (après normalisation casse + espaces) dans la FTM. Sinon
    l'écart est suspect — on conserve l'anomalie mais on dégrade la confiance."""
    if not extrait:
        return False
    return _normalize_for_verify(extrait) in _normalize_for_verify(text)


def _load_custom_rules(configuration: dict | None = None) -> list[dict]:
    """Règles personnalisées valides (consigne non vide, validées, activées).

    Deux filtres indépendants excluent une règle de l'analyse :
    - `validated=False` : file de validation — une règle importée par checklist
      attend une validation humaine avant de participer à l'analyse.
    - `enabled=False` : interrupteur d'activation en direct — l'utilisateur peut
      désactiver une règle sans la supprimer (elle reste éditable / réactivable).

    Les champs `validated` / `enabled` absents valent « vrai » → compat
    ascendante (règles saisies à la main ou créées avant ces champs).
    """
    out: list[dict] = []
    source = configuration if configuration is not None else load_rules()
    for r in (source.get("regles_personnalisees") or []):
        if not isinstance(r, dict):
            continue
        if r.get("validated") is False:
            continue
        if r.get("enabled") is False:
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
    """Remplace chaque `{nom}` de la consigne par les valeurs de la colonne
    homonyme du projet — registre de reference (`reference_columns`) d'abord,
    registre BASL (`basl_columns`) en repli. Un `{nom}` sans colonne
    correspondante est laisse tel quel (l'IA le verra comme du texte)."""
    def _values_for(name: str) -> tuple[str, list[str]] | None:
        """(source_label, valeurs) de la colonne `name`, ou None si inconnue."""
        col = reference_column(project, name)
        if col is not None:
            return "reference", reference_column_values(
                project.reference_path, col.get("sheet", ""), col.get("column", ""),
            )
        col = basl_column(project, name)
        if col is not None:
            return "BASL", reference_column_values(
                project.basl_path, col.get("sheet", ""), col.get("column", ""),
            )
        return None

    def _sub(match: re.Match[str]) -> str:
        name = match.group(1)
        resolved = _values_for(name)
        if resolved is None:
            return match.group(0)
        source, values = resolved
        if not values:
            return f"[colonne {source} « {name} » : aucune valeur]"
        shown = values[:_MAX_PLACEHOLDER_VALUES]
        extra = len(values) - len(shown)
        suffix = f" (+{extra} autres)" if extra > 0 else ""
        return f"[colonne {source} « {name} » : {', '.join(shown)}{suffix}]"

    return _PLACEHOLDER_RE.sub(_sub, consigne)


def active_custom_rule_count() -> int:
    """Nombre de regles qui seraient reellement evaluees (validees + activees +
    consigne non vide), independamment de la disponibilite du LLM. Utilise par
    `analysis.py` pour signaler qu'une analyse « 0 regle » n'a RIEN verifie,
    plutot que de laisser 0 anomalie ressembler a un livrable conforme."""
    return len(_load_custom_rules())


def run_custom_rules(
    db: Session,
    project: Project,
    run_id: uuid.UUID,
    mistral: MistralClient | None = None,
    *,
    only_file_ids: set[uuid.UUID] | None = None,
    stats: RuleEvaluationStats | None = None,
) -> list[Anomaly]:
    """Évalue les règles personnalisées actives contre chaque fichier du projet.
    `only_file_ids` (optionnel) restreint l'analyse à un échantillon de fichiers
    (réanalyse ciblée) ; `None` = tous les fichiers."""
    configuration = load_rules()
    rules = _load_custom_rules(configuration)
    if stats is not None:
        stats.active_rules = len(rules)
        digest_input = json.dumps(
            {
                "rules": rules,
                "instructions": (configuration.get("instructions_libres") or "").strip(),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        stats.rule_set_sha256 = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
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
        if only_file_ids is not None and f.id not in only_file_ids:
            continue
        latest = latest_version(f)
        if latest is None:
            continue
        text = (latest.extracted_text or "").strip()
        if not text:
            continue
        if stats is not None:
            stats.evaluation_calls += 1
        items, succeeded = _llm_eval(
            mistral,
            text,
            rules,
            (configuration.get("instructions_libres") or "").strip(),
        )
        if stats is not None:
            if succeeded:
                stats.files_evaluated += 1
                stats.rules_evaluated += len(rules)
                stats.evaluated_file_ids.add(f.id)
            else:
                stats.evaluation_failures += 1
        for item in items:
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
                "",
                confidence=confidence,
                category=label,
                evidence=extrait,
            )
            db.add(a)
            anomalies.append(a)

    return anomalies


def _llm_eval(
    mistral: MistralClient,
    text: str,
    rules: list[dict],
    general_instructions: str = "",
) -> tuple[list[dict], bool]:
    """Soumet les règles personnalisées + le contenu FTM à Mistral.
    Renvoie les écarts et indique si l'appel a abouti."""
    # Contenu de document non fiable -> neutralise les sequences d'injection
    # (tokens speciaux, delimiteurs d'instruction) avant de l'envoyer au LLM.
    text = sanitize_document(text)
    excerpt = text if len(text) <= _MAX_TEXT else text[:_MAX_TEXT] + "\n[...document tronqué...]"
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
        + (f"Consignes générales : {general_instructions}. " if general_instructions else "")
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
        if not isinstance(result, dict) or not isinstance(result.get("anomalies"), list):
            raise ValueError("Invalid custom-rule response shape")
        return [x for x in result["anomalies"] if isinstance(x, dict)], True
    except Exception as exc:
        log.exception(
            "custom_rule_evaluation_failed",
            error_type=type(exc).__name__,
            rule_count=len(rules),
            text_length=len(text),
        )
        return [], False
