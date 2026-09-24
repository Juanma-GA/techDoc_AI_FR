"""Compile one imported checklist row into a strict CompiledRule."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, get_args

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.checks.client_bundle import ClientBundle, validate_compiled_rule_mapping
from app.core.compiled_rules import CompiledRule, DocumentMetaField, RuleTarget
from app.core.errors import AppError
from app.core.excel_rules import ParsedRule
from app.core.llm_suggester import call_chat
from app.core.primitive_catalog import primitive_catalog_for_prompt


_ALLOWED_META_FIELDS = set(get_args(DocumentMetaField))
_PRIMITIVE_CATALOG = primitive_catalog_for_prompt()


CHECKLIST_COMPILER_SYSTEM_PROMPT = """Tu es un compilateur de règles de conformité documentaire.
Ta mission est de convertir une règle en langage naturel en une règle JSON exécutable par un backend déterministe.
Tu ne contrôles pas le document. Tu ne décides pas si le document est conforme. Tu transformes uniquement la règle fournie.

Tu choisis uniquement des primitives du catalogue fermé fourni dans l'entrée `primitive_catalog`.
Tu ne crées jamais de primitive, de fonction Python ou d'identifiant de référence qui n'y figure pas.
Le catalogue décrit les capacités disponibles et leurs types ; il ne contient aucune valeur d'un document.

PRIORITÉ ABSOLUE : préfère TOUJOURS execution=deterministic quand la règle peut se ramener à une présence, une
absence, une égalité, un motif (regex) ou une comparaison de valeurs — même si tu ne connais pas cette règle à
l'avance. N'utilise semantic QUE quand une compréhension du sens, du ton ou d'un jugement contextuel est
réellement nécessaire (style rédactionnel, cohérence narrative, ambiguïté de sens). La plupart des règles de
checklist documentaire (mentions obligatoires, termes interdits, remplacement de terme, cohérence entre deux
zones, présence conditionnelle) SONT déterministes : ne bascule pas en semantic par facilité.

Utilise uniquement ces valeurs :
execution: deterministic | semantic | manual | unsupported
field pour document_text : text | page_number | document_type | important_notice ou une cle de client_mapping.entities.
field pour document_meta et only_if : une cle de client_mapping.fields.
operator: exists | not_exists | equals | regex | regex_exists | normalized_equals | contains_any | contains_all | contains_none | equals_field | font_size_equals
expected: valeur attendue du contrôle ; une chaîne pour exists/not_exists/equals/regex/regex_exists/normalized_equals, un nombre de points pour font_size_equals,
  une LISTE de chaînes pour contains_any/contains_all/contains_none, absent (null) pour equals_field.
  N'utilise jamais la clé `value`.

ATTENTION, piege frequent : `regex` et `regex_exists` sont DES OPERATEURS OPPOSES, ne les confonds jamais.
- `regex` = motif INTERDIT : échoue (FAIL) si le motif EST trouvé dans le texte. Réservé aux tournures a
  proscrire (ex. voix passive, formulation ambigue).
- `regex_exists` = motif OBLIGATOIRE : échoue (FAIL) si le motif N'EST PAS trouvé. Utilise CELUI-CI des que la
  règle dit qu'un texte (éventuellement avec une partie variable, ex. une année) DOIT être présent. Compiler
  une mention obligatoire avec `regex` inverse le sens de la règle : le texte correct serait systématiquement
  signalé comme une violation.

Vocabulaire déterministe disponible (choisis l'opérateur le plus proche du besoin plutôt que de renoncer) :
- Mention obligatoire (un texte doit être présent) -> field=text, operator=exists, expected="texte exact".
- Terme interdit (un mot ne doit jamais apparaître) -> field=text, operator=not_exists, expected="terme".
- Liste de termes interdits (aucun de ces mots ne doit apparaître) -> operator=contains_none, expected=["terme1","terme2",...].
- Liste de synonymes acceptés (au moins un doit apparaître) -> operator=contains_any, expected=["terme1","terme2",...].
- Plusieurs mentions toutes obligatoires -> operator=contains_all, expected=["mention1","mention2",...].
- Taille de police d'une entite declaree -> utilise la cle de cette entite comme field avec
    operator=font_size_equals et une valeur en points.
- Toute valeur introduite par « ex: », « exemple » ou entre parenthèses est une illustration, pas une
    valeur littérale. Déduis la structure invariante de la règle et écris dans `expected` le regex complet,
    avec les séparateurs, espaces optionnels et parties variables nécessaires. Le backend n'élargit ni ne
    corrige ensuite le motif produit.
- Motif variable (texte avec une partie qui change, ex. une plage d'années) qui DOIT être présent ->
  operator=regex_exists, expected="regex Python". N'utilise JAMAIS operator=regex pour ce cas (voir
  l'avertissement ci-dessus) : `regex` est réservé a un motif qui ne doit PAS apparaître.
- Motif regex qui doit contenir une valeur saisie dans le contexte du document -> utilise un placeholder
    litteral `{{nom_du_champ}}` dans expected, uniquement pour un champ de `client_mapping.fields`.
    Le backend remplace ce placeholder par la valeur du document courant; si la valeur manque, le resultat
    est INCONCLUSIVE. N'invente jamais la valeur. Pour une comparaison de champs extraits, prefere
    `equals_field` et `compare_to`.
- Remplacement automatique proposé quand la règle décrit une correction évidente (X doit être remplacé par Y,
  un terme interdit a un équivalent autorisé) -> ajoute "replacement":"texte de remplacement" (avec un seul
  terme/regex) ou "replacements":{"terme_interdit":"remplacement", ...} (avec une liste, un remplacement par
  terme). N'invente jamais un remplacement si la règle n'en donne pas un clairement déductible ; laisse le champ
  absent plutôt que de deviner.
- Comparaison entre deux zones ou avec une donnée du document (ex. l'année de fin dans le copyright doit
  correspondre à l'année de révision du document) -> operator=equals_field, expected=null, et
  "compare_to":{"source":"document_text"|"document_meta","field":"...","page":"...","region":"...",
  "normalization":[...]}.
  - source=document_text : relit un autre champ/zone du document (mêmes valeurs que field ci-dessus), avec sa
    propre page/region (ex. {"page":"all","region":"full_page"}).
    - source=document_meta : lit une donnée structurée saisie pour CE document (pas une valeur du texte).
        Utilise uniquement les champs declares dans `client_mapping.fields`.
  - normalization accepte : unicode, trim, spaces, line_breaks, et "extract_year" (extrait une année sur 4
    chiffres, ou étend un suffixe à 2 chiffres en 20XX — utile pour comparer "MAR 18/26" à "2000-2026").
    - Exemple générique : le pied de page (region=footer) contient un copyright avec une plage d'années
        variable (les valeurs « 2000 » et « 2026 » dans l'exemple sont illustratives), et la deuxième année doit
        correspondre à l'année de révision saisie pour le document. Compile deux checks : (1) operator=regex_exists
        sur field=text pour vérifier la présence du texte de copyright avec un motif d'années variable
        (ex. "©\\s*\\d{4}-(\\d{4})") — PAS operator=regex, qui ferait échouer ce check pour CHAQUE document,
        même correct ; (2) operator=equals_field, field=copyright_end_year,
    compare_to={"source":"document_meta","field":"meta_revision_date","normalization":["extract_year"]}.
- Une contrainte arithmétique comme « le numéro de révision précédente + 1 » n'est pas exprimable par
    le vocabulaire déterministe actuel. Utilise execution=semantic si la révision précédente est visible
    dans le texte et peut être évaluée avec le contexte du document; sinon utilise execution=unsupported
    avec compilation_error explicite. Ne la remplace jamais par un regex sur un numéro d'exemple.
- Présence conditionnelle (une règle qui ne s'applique que si une donnée du document existe) -> ajoute au
    niveau de la règle (pas du check) "only_if":{"field":"nom_du_champ","state":"present"} (ou "absent").
    only_if.field doit être une cle de `client_mapping.fields`.

Les références documentaires sont décrites par leurs identifiants uniquement. Le compilateur ne reçoit
aucune valeur d'un document particulier. Une valeur concrète sera fournie au runtime, pendant l'analyse
du document, et doit être résolue depuis les métadonnées du document courant. Ne recopie jamais une valeur
de contexte dans la règle compilée et ne fabrique jamais une valeur absente.

Si la règle indique explicitement une vérification humaine, utilise manual et renseigne manual_instruction.
Si la règle nécessite de comprendre le sens, le contexte ou une conformité que le vocabulaire déterministe
ci-dessus ne peut vraiment pas exprimer, utilise semantic et renseigne semantic_instruction avec la question à
poser au modèle.
Si la règle est ambiguë ou dépasse le vocabulaire autorisé, utilise unsupported et renseigne compilation_error
en nommant précisément ce qui manque.
Ne complète jamais une information absente. Retourne uniquement un JSON valide correspondant au schéma CompiledRule, sans aucun texte hors JSON.
La réponse doit être plate à la racine: id, topic, execution, target, checks, source, origin_ref et,
optionnellement, only_if, primitive_plan, hypotheses, valid_examples, invalid_examples et prerequisites.
Chaque étape de primitive doit avoir exactement la forme
{"step_id":"step_1","primitive":"select.target","parameters":{...},"input_from":{...}}.
`primitive` contient l'identifiant du catalogue ; n'utilise pas la clé `id` pour une étape.
N'utilise pas d'enveloppe required_metadata/rules."""


_REGION_ALIASES = {
    "": "full_page",
    "full_page": "full_page",
    "page": "full_page",
    "header": "header",
    "en-tete": "header",
    "en-tête": "header",
    "entete": "header",
    "body": "body",
    "corps": "body",
    "footer": "footer",
    "pied de page": "footer",
}
_MANUAL_HANDLING = {"manuel", "manual", "humain", "human", "a la main", "à la main"}


def checklist_rule_id(origin_ref: str) -> str:
    digest = hashlib.sha256(origin_ref.encode("utf-8")).hexdigest()[:12].upper()
    return f"CHECKLIST_{digest}"


def _normalize_primitive_plan(payload: dict[str, object]) -> None:
    raw_plan = payload.get("primitive_plan")
    if raw_plan is None:
        return
    if not isinstance(raw_plan, list):
        raise ValueError("primitive_plan doit être une liste")

    normalized_plan: list[object] = []
    for index, raw_step in enumerate(raw_plan, start=1):
        if not isinstance(raw_step, dict):
            normalized_plan.append(raw_step)
            continue
        step = dict(raw_step)
        catalog_id = step.pop("id", None)
        primitive = step.get("primitive")
        if catalog_id is not None:
            if primitive is not None and primitive != catalog_id:
                raise ValueError("primitive_plan contient id et primitive contradictoires")
            step["primitive"] = catalog_id
        step.setdefault("step_id", f"step_{index}")
        if "parameters" not in step and "params" in step:
            step["parameters"] = step.pop("params")
        normalized_plan.append(step)
    payload["primitive_plan"] = normalized_plan


def _normalize_compiler_payload(
    payload: object,
    *,
    fallback_target: RuleTarget,
    fallback_topic: str,
    fallback_instruction: str,
    allowed_meta_fields: set[str] | None = None,
) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("la réponse du compilateur doit être un objet JSON")

    normalized = dict(payload)
    metadata = normalized.pop("required_metadata", None)
    wrapped_rules = normalized.pop("rules", None)
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise ValueError("required_metadata doit être un objet")
        for key in ("id", "topic", "source", "origin_ref"):
            if key not in normalized and key in metadata:
                normalized[key] = metadata[key]

    if wrapped_rules is not None:
        if "checks" in normalized:
            raise ValueError("la réponse contient à la fois rules et checks")
        normalized["checks"] = wrapped_rules

    _normalize_primitive_plan(normalized)

    raw_checks = normalized.get("checks")
    semantic_parts: list[str] = []
    if raw_checks is not None:
        if not isinstance(raw_checks, list):
            raise ValueError("checks doit être une liste")
        checks: list[object] = []
        for raw_check in raw_checks:
            if not isinstance(raw_check, dict):
                checks.append(raw_check)
                continue
            check = dict(raw_check)
            embedded_instruction = check.pop("semantic_instruction", None)
            if embedded_instruction:
                semantic_parts.append(str(embedded_instruction).strip())
            if "value" in check:
                if "expected" not in check:
                    check["expected"] = check["value"]
                check.pop("value", None)
            compare_to = check.get("compare_to")
            if (
                allowed_meta_fields is None
                and
                isinstance(compare_to, dict)
                and compare_to.get("source") == "document_meta"
                and compare_to.get("field") not in _ALLOWED_META_FIELDS
            ):
                # Same mix-up as only_if.field (a Check.field value leaking
                # into a document_meta reference) — the check can't express
                # the comparison at all without a valid compare_to, so drop
                # the whole check rather than crash the rule.
                continue
            if check or not embedded_instruction:
                checks.append(check)
        normalized["checks"] = checks

    if semantic_parts:
        existing_instruction = normalized.get("semantic_instruction")
        instructions = [str(existing_instruction).strip()] if existing_instruction else []
        instructions.extend(part for part in semantic_parts if part)
        if normalized.get("checks"):
            instructions.append(
                "Contrôles structurés complémentaires : "
                + json.dumps(normalized["checks"], ensure_ascii=False)
            )
        normalized["semantic_instruction"] = "\n".join(instructions)
        normalized["checks"] = []
        normalized["execution"] = "semantic"

    if normalized.get("semantic_instruction") and normalized.get("checks"):
        normalized["semantic_instruction"] = (
            str(normalized["semantic_instruction"]).strip()
            + "\nContrôles structurés complémentaires : "
            + json.dumps(normalized["checks"], ensure_ascii=False)
        )
        normalized["checks"] = []
        normalized["execution"] = "semantic"

    normalized.setdefault("topic", fallback_topic)
    # `target` is fully determined by the imported row's zone column
    # (resolved before the LLM call) — enforce it rather than trust the
    # model's echo, which used to fail the whole rule on any drift.
    normalized["target"] = fallback_target.model_dump(mode="json")
    only_if = normalized.get("only_if")
    if (
        allowed_meta_fields is None
        and isinstance(only_if, dict)
        and only_if.get("field") not in _ALLOWED_META_FIELDS
    ):
        # The model sometimes reuses a `Check.field` value (e.g. document_type)
        # that isn't a valid document_meta field — drop the condition instead
        # of failing the whole rule; the check simply always applies.
        normalized["only_if"] = None
    if "execution" not in normalized:
        if normalized.get("checks"):
            normalized["execution"] = "deterministic"
        elif normalized.get("semantic_instruction"):
            normalized["execution"] = "semantic"
    if normalized.get("execution") == "semantic" and not normalized.get("semantic_instruction"):
        normalized["semantic_instruction"] = fallback_instruction
    return normalized


def compile_checklist_rule(
    db: Session,
    parsed: ParsedRule,
    filename: str,
    *,
    chat: Callable[..., str] | None = None,
    client_bundle: ClientBundle[Any] | None = None,
) -> CompiledRule:
    origin_ref = f"{filename}:{parsed.sheet}:{parsed.row_number}"
    rule_id = checklist_rule_id(origin_ref)
    normalized_zone = parsed.target_zone.strip().lower()
    region = _REGION_ALIASES.get(normalized_zone)
    target = RuleTarget(page="all", region=region or "full_page")
    expected_manual = parsed.handling in _MANUAL_HANDLING
    zone_instruction = (
        f'La zone "{parsed.target_zone}" ne correspond à aucune region autorisée; '
        "la règle doit être unsupported et nommer cette region manquante."
        if region is None
        else f'Utilise exactement target={{"page":"all","region":"{region}"}}.'
    )
    client_mapping_payload = (
        {
            "fields": {
                name: definition.model_dump(mode="json")
                for name, definition in client_bundle.mapping.fields.items()
            },
            "entities": dict(client_bundle.mapping.entities),
            "tokens": dict(client_bundle.mapping.tokens),
            "operations": sorted(client_bundle.operations),
        }
        if client_bundle is not None
        else None
    )
    allowed_meta_fields = set(client_bundle.mapping.fields) if client_bundle is not None else None
    user_prompt = json.dumps(
        {
            "required_metadata": {
                "id": rule_id,
                "topic": parsed.category or "Checklist",
                "source": "user_checklist",
                "origin_ref": origin_ref,
            },
            "mapped_input": {
                "check": parsed.check,
                "handling": parsed.handling,
                "zone": parsed.target_zone,
                "context": parsed.context,
            },
            "primitive_catalog": _PRIMITIVE_CATALOG,
            "client_mapping": client_mapping_payload,
            "constraints": [
                zone_instruction,
                "Recopie required_metadata sans modification dans la réponse.",
                "Une prise en compte manuelle impose execution=manual.",
                "Utilise uniquement les identifiants et références du primitive_catalog; n'attends aucune valeur concrète pendant l'import.",
                "Les champs de document_text viennent des champs generiques et de client_mapping.entities; les champs document_meta et only_if viennent uniquement de client_mapping.fields.",
                "Les operations de client_mapping.operations sont les seules operations client autorisees.",
            ],
        },
        ensure_ascii=False,
    )
    try:
        response = (chat or call_chat)(db, CHECKLIST_COMPILER_SYSTEM_PROMPT, user_prompt, temperature=0.0)
        payload = _normalize_compiler_payload(
            json.loads(response),
            fallback_target=target,
            fallback_topic=parsed.category or "Checklist",
            fallback_instruction=parsed.message,
            allowed_meta_fields=allowed_meta_fields,
        )
        rule = CompiledRule.model_validate(payload)
        if (rule.id, rule.source, rule.origin_ref) != (rule_id, "user_checklist", origin_ref):
            raise ValueError("id, source ou origin_ref ne correspond pas à la ligne importée")
        if region is None and rule.execution != "unsupported":
            raise ValueError(f'region non supportée: "{parsed.target_zone}"')
        if expected_manual and rule.execution != "manual":
            raise ValueError("la prise en compte manuelle exige execution=manual")
        if client_bundle is not None:
            validate_compiled_rule_mapping(rule, client_bundle.mapping)
            unknown_operations = {
                check.operation
                for check in rule.checks
                if check.operator == "client_operation"
                and check.operation not in client_bundle.operations
            }
            if unknown_operations:
                names = ", ".join(sorted(str(name) for name in unknown_operations))
                raise ValueError(f"operations client non declarees: {names}")
        rule = rule.model_copy(update={"source_instruction": parsed.message})
        rule.severity = parsed.severity if parsed.severity in {"info", "warning", "error"} else "warning"
        return rule
    except (AppError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        return CompiledRule(
            id=rule_id,
            topic=parsed.category or "Checklist",
            severity=parsed.severity if parsed.severity in {"info", "warning", "error"} else "warning",
            execution="unsupported",
            target=target,
            checks=[],
            compilation_error=f"Réponse du compilateur invalide: {exc}",
            source="user_checklist",
            origin_ref=origin_ref,
            source_instruction=parsed.message,
        )