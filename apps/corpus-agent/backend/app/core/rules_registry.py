"""Registry déclaratif des règles métier — fondation de la fiabilité v5.

Chaque règle est une donnée déclarative typée : id stable, paramètres avec
défauts, sévérité, dépendances runtime, exemples documentaires. Les checks
(`app/checks/*.py`) déclarent leurs règles via `register(Rule(...))`, à côté
du code qui les consomme — pas de défauts en doublon dans `rules.py`.

Au runtime, `resolve_rules()` produit, pour chaque règle déclarée, son état
résolu (`ResolvedRule` : enabled + params, après application des overrides
utilisateur depuis `data/rules.json`). Les checks consomment uniquement le
résolu, jamais le brut JSON.

Le format d'override JSON cible est *sparse* :
    {
      "<rule.id>": {
        "enabled": bool,            # optionnel, défaut = rule.enabled_default
        "params":  { "<name>": <v>, ... }   # optionnel, sparse aussi
      }
    }
Tant que la migration depuis le format legacy n'est pas faite (phase 4),
chaque règle expose un `legacy_resolver` qui sait extraire son état depuis
le `rules.json` legacy. C'est l'unique pont de compat.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional


# ----------------------------------------------------------------------------
# Types
# ----------------------------------------------------------------------------

RuleType = Literal[
    "bool", "int", "float", "string", "regex", "enum",
    "list[str]", "map[str,str]",
]
Severity = Literal["low", "medium", "high"]
Capability = Literal[
    "mistral_chat", "mistral_vision", "mistral_embeddings",
    "parser_xlsm", "parser_pdf", "parser_docx",
]


# ----------------------------------------------------------------------------
# Dataclasses
# ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Example:
    """Cas d'entrée illustratif (texte ou description courte). Sert à la
    fois de doc UI, de fixture mentale pour le développeur, et de socle aux
    futurs tests CI. `valid=True` ⇒ la règle ne doit PAS émettre d'anomalie
    sur ce cas ; `False` ⇒ elle doit en émettre."""
    text: str
    valid: bool
    note_key: str = ""


@dataclass(frozen=True)
class ParamSchema:
    """Schéma d'un paramètre d'une règle. Le nom du paramètre est la clé
    dans `Rule.params` ; ce schéma porte type, défaut, label i18n et
    validateur."""
    type: RuleType
    default: Any
    name_key: str
    validator: Optional[Callable[[Any], None]] = None
    constraints: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class Rule:
    """Déclaration immutable d'une règle métier.

    Une règle = un check logique qui peut émettre un ou plusieurs types
    d'anomalies, avec 0..N paramètres. Le toggle `enabled` est **séparé**
    des paramètres : désactiver une règle ne perd pas ses paramètres
    tweakés.
    """
    id: str
    family: str
    name_key: str
    description_key: str
    severity: Severity = "medium"
    anomaly_types: tuple[str, ...] = ()
    requires: tuple[Capability, ...] = ()
    enabled_default: bool = True
    params: dict[str, ParamSchema] = field(default_factory=dict)
    examples: tuple[Example, ...] = ()
    legacy_resolver: Optional[Callable[[dict], tuple[bool, dict[str, Any]]]] = None
    """Pont de compat (LECTURE) : prend le `rules.json` legacy et renvoie
    `(enabled, params)`. Phase 4 le supprimera."""
    legacy_keys: dict[str, str] = field(default_factory=dict)
    """Pont de compat (ÉCRITURE) : `{param_name → legacy_key_in_family}`.
    Permet de convertir un override sparse en mutation du `rules.json`
    legacy. Vide = règle sans paramètres écrits (toggle uniquement)."""
    legacy_enabled_key: Optional[str] = None
    """Clé legacy (dans la famille) qui porte le toggle `enabled`. `None`
    = pas de toggle dédié dans le legacy (la règle est toujours active
    en pratique, l'UI peut quand même la désactiver mais ça ne sera
    pas persistant sur cette version du legacy)."""


@dataclass(frozen=True)
class ResolvedRule:
    """État effectif d'une règle au runtime : enabled + params résolus
    (override appliqué sur les défauts). Consommé par les checks."""
    rule: Rule
    enabled: bool
    params: dict[str, Any]


# ----------------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------------

_REGISTRY: dict[str, Rule] = {}


def register(rule: Rule) -> Rule:
    """Enregistre une règle dans le registry global. Lève si l'`id` est
    déjà pris (collision = bug à corriger, jamais à ignorer)."""
    if rule.id in _REGISTRY:
        raise ValueError(f"Rule id déjà enregistrée : {rule.id!r}")
    _REGISTRY[rule.id] = rule
    return rule


def all_rules() -> list[Rule]:
    """Toutes les règles enregistrées, dans l'ordre d'enregistrement."""
    return list(_REGISTRY.values())


def get_rule(rule_id: str) -> Optional[Rule]:
    return _REGISTRY.get(rule_id)


# ----------------------------------------------------------------------------
# Résolution (overrides → ResolvedRule)
# ----------------------------------------------------------------------------

def _apply_sparse(rule: Rule, override: dict) -> ResolvedRule:
    """Applique un override au format sparse cible :
    `{enabled: bool?, params: {name: val, ...}?}`."""
    enabled = bool(override.get("enabled", rule.enabled_default))
    param_overrides = override.get("params") or {}
    params: dict[str, Any] = {}
    for name, schema in rule.params.items():
        params[name] = param_overrides.get(name, schema.default)
    return ResolvedRule(rule=rule, enabled=enabled, params=params)


_RULE_STATE_KEY = "_rule_state"
"""Slot dédié dans le `rules.json` legacy pour persister le toggle `enabled`
des règles qui n'ont pas de clé booléenne native dans le legacy (ex.
illustrations.dimensions, script.format, …). Format :
    "_rule_state": {"<rule.id>": {"enabled": true|false}}
Si la règle a un `legacy_enabled_key`, c'est celui-ci qui prime. Sinon
`_rule_state[rule.id].enabled` ; sinon `enabled_default` du registry."""


def _apply_legacy(rule: Rule, legacy_rules: dict) -> ResolvedRule:
    """Applique un override depuis le format `rules.json` legacy via le
    `legacy_resolver` de la règle. Si la règle n'a pas de resolver legacy,
    on retourne ses défauts (= règle non encore migrée côté config).

    L'`enabled` final tient compte de `_rule_state[rule.id].enabled` si
    présent (priorité maximale, override stocké par le sparse PUT)."""
    if rule.legacy_resolver is None:
        return ResolvedRule(
            rule=rule, enabled=_resolve_enabled(rule, legacy_rules, rule.enabled_default),
            params={n: s.default for n, s in rule.params.items()},
        )
    try:
        enabled, params = rule.legacy_resolver(legacy_rules)
    except Exception:  # noqa: BLE001 — défensif : un resolver KO ne doit pas
                       # crasher le moteur ; on retombe sur les défauts.
        return ResolvedRule(
            rule=rule, enabled=_resolve_enabled(rule, legacy_rules, rule.enabled_default),
            params={n: s.default for n, s in rule.params.items()},
        )
    # Complète les paramètres absents avec les défauts.
    resolved_params: dict[str, Any] = {}
    for name, schema in rule.params.items():
        resolved_params[name] = params.get(name, schema.default)
    # `_rule_state` override le résultat du resolver (utile pour les règles
    # sans `legacy_enabled_key` natif).
    final_enabled = _resolve_enabled(rule, legacy_rules, bool(enabled))
    return ResolvedRule(rule=rule, enabled=final_enabled, params=resolved_params)


def _resolve_enabled(rule: Rule, legacy_rules: dict, default: bool) -> bool:
    """Lit l'éventuel override `_rule_state[rule.id].enabled`. Si absent ou
    invalide, retourne `default` (typiquement le résultat du legacy_resolver
    ou le `enabled_default`)."""
    state = legacy_rules.get(_RULE_STATE_KEY) if isinstance(legacy_rules, dict) else None
    if not isinstance(state, dict):
        return default
    entry = state.get(rule.id)
    if not isinstance(entry, dict) or "enabled" not in entry:
        return default
    return bool(entry["enabled"])


def resolve_rules(
    overrides: Optional[dict] = None,
    *,
    legacy: bool = True,
) -> dict[str, ResolvedRule]:
    """Résout toutes les règles du registry contre un dict d'overrides.

    - `legacy=True` (défaut tant que phase 4 non livrée) : `overrides` est
      le format legacy (dict famille→clés plats). Chaque règle utilise son
      `legacy_resolver`.
    - `legacy=False` : `overrides` est au format sparse cible
      `{rule_id: {enabled, params}}`.

    Sans `overrides`, charge `app.core.rules.load_rules()` (legacy).
    """
    if overrides is None:
        from app.core.rules import load_rules  # import local pour éviter cycle
        overrides = load_rules()
    out: dict[str, ResolvedRule] = {}
    for rid, rule in _REGISTRY.items():
        if legacy:
            out[rid] = _apply_legacy(rule, overrides)
        else:
            out[rid] = _apply_sparse(rule, overrides.get(rid, {}))
    return out


# ----------------------------------------------------------------------------
# Catalogue (sérialisable pour l'API + UI auto-gen)
# ----------------------------------------------------------------------------

def to_catalog() -> list[dict[str, Any]]:
    """Sérialise le registry pour `GET /api/v1/rules/catalog`. Les callables
    (validators, legacy_resolver) sont omis — seules les métadonnées
    consommables côté UI/i18n sont exposées."""
    return [
        {
            "id": r.id,
            "family": r.family,
            "name_key": r.name_key,
            "description_key": r.description_key,
            "severity": r.severity,
            "anomaly_types": list(r.anomaly_types),
            "requires": list(r.requires),
            "enabled_default": r.enabled_default,
            "params": {
                name: {
                    "type": ps.type,
                    "default": ps.default,
                    "name_key": ps.name_key,
                    "constraints": ps.constraints or {},
                }
                for name, ps in r.params.items()
            },
            "examples": [
                {"text": e.text, "valid": e.valid, "note_key": e.note_key}
                for e in r.examples
            ],
            "legacy_keys": dict(r.legacy_keys),
            "legacy_enabled_key": r.legacy_enabled_key,
        }
        for r in _REGISTRY.values()
    ]


def sparse_to_legacy(sparse: dict, base_legacy: dict) -> dict:
    """Convertit un override sparse `{rule_id: {enabled, params}}` en
    mutation du `base_legacy` (format `rules.json` actuel). Le `base_legacy`
    sert de point de départ — les clés non couvertes par le sparse sont
    conservées telles quelles (custom rules, instructions_libres, …).

    Lève `KeyError` si un `rule_id` est inconnu — l'appelant doit valider
    via `validate_sparse_overrides` d'abord.
    """
    import copy as _copy
    legacy = _copy.deepcopy(base_legacy or {})
    for rid, ov in (sparse or {}).items():
        rule = _REGISTRY.get(rid)
        if rule is None:
            raise KeyError(f"Rule inconnue : {rid}")
        fam = legacy.setdefault(rule.family, {})
        if not isinstance(fam, dict):
            # Le legacy a un type inattendu sur la famille — on l'écrase
            # plutôt que de planter (l'UI auto-gen a le dernier mot).
            fam = {}
            legacy[rule.family] = fam
        enabled_val = bool(ov.get("enabled", rule.enabled_default))
        if rule.legacy_enabled_key is not None:
            # Le legacy a une clé booléenne native pour cette règle.
            fam[rule.legacy_enabled_key] = enabled_val
        else:
            # Pas de slot natif : on stocke dans `_rule_state` pour que
            # `_resolve_enabled` puisse le relire au prochain analyze.
            state = legacy.setdefault(_RULE_STATE_KEY, {})
            if not isinstance(state, dict):
                state = {}
                legacy[_RULE_STATE_KEY] = state
            state[rid] = {"enabled": enabled_val}
        params = ov.get("params") or {}
        for pname, legacy_key in rule.legacy_keys.items():
            if pname in params:
                fam[legacy_key] = params[pname]
    return legacy


# ----------------------------------------------------------------------------
# Validation des overrides (format sparse uniquement — utilisé par PUT)
# ----------------------------------------------------------------------------

class RuleValidationError(ValueError):
    """Validation refusée. `errors` détaille les violations par rule.id."""

    def __init__(self, errors: dict[str, list[str]]) -> None:
        self.errors = errors
        super().__init__(f"Validation rules KO : {errors}")


def _validate_value(schema: ParamSchema, value: Any) -> Optional[str]:
    """Vérifie qu'une valeur respecte un `ParamSchema`. Retourne un message
    d'erreur, ou `None` si OK."""
    t = schema.type
    if t == "bool":
        if not isinstance(value, bool):
            return f"attendu bool, reçu {type(value).__name__}"
    elif t == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            return f"attendu int, reçu {type(value).__name__}"
        c = schema.constraints or {}
        if "min" in c and value < c["min"]:
            return f"< min={c['min']}"
        if "max" in c and value > c["max"]:
            return f"> max={c['max']}"
    elif t == "float":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return f"attendu float, reçu {type(value).__name__}"
    elif t == "string":
        if not isinstance(value, str):
            return f"attendu string, reçu {type(value).__name__}"
        c = schema.constraints or {}
        if "max_length" in c and len(value) > c["max_length"]:
            return f"longueur > {c['max_length']}"
    elif t == "regex":
        if not isinstance(value, str):
            return f"attendu string regex, reçu {type(value).__name__}"
        try:
            re.compile(value)
        except re.error as e:
            return f"regex invalide : {e}"
    elif t == "enum":
        c = schema.constraints or {}
        choices = c.get("choices") or ()
        if value not in choices:
            return f"valeur {value!r} hors choix {list(choices)}"
    elif t == "list[str]":
        if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
            return "attendu list[str]"
    elif t == "map[str,str]":
        if not isinstance(value, dict) or any(
            not isinstance(k, str) or not isinstance(v, str)
            for k, v in value.items()
        ):
            return "attendu map[str,str]"
    if schema.validator is not None:
        try:
            schema.validator(value)
        except Exception as e:  # noqa: BLE001
            return str(e) or "validateur KO"
    return None


def detect_capabilities(mistral_settings: Optional[dict] = None) -> set[Capability]:
    """Capabilités disponibles au runtime, pour décider si une règle est
    exécutable (sa liste `requires` doit être incluse dans le retour).

    - `parser_xlsm` / `parser_pdf` / `parser_docx` : toujours présentes
      (les parsers sont importés au boot, pas de feature flag runtime).
    - `mistral_*` : présentes si la conf Mistral expose la clé API et le
      modèle correspondant. Si `mistral_settings` n'est pas fourni,
      retourne uniquement les capacités parsers (vue conservative)."""
    caps: set[Capability] = {"parser_xlsm", "parser_pdf", "parser_docx"}
    if not mistral_settings:
        return caps
    if mistral_settings.get("api_key"):
        if mistral_settings.get("chat_model"):
            caps.add("mistral_chat")
        if mistral_settings.get("embed_model"):
            caps.add("mistral_embeddings")
        if mistral_settings.get("vision_model"):
            caps.add("mistral_vision")
    return caps


def rule_is_runnable(rule: Rule, caps: set[Capability]) -> bool:
    """Une règle est exécutable ssi toutes ses `requires` sont présentes
    dans les capacités runtime. Utilisée par les checks pour skipper
    silencieusement et par l'UI pour griser les règles non disponibles."""
    return all(c in caps for c in rule.requires)


def validate_sparse_overrides(overrides: dict) -> None:
    """Vérifie qu'un dict d'overrides au format sparse respecte le schéma
    de toutes les règles connues. Lève `RuleValidationError` si une ou
    plusieurs entrées sont invalides. Les rule_ids inconnus sont signalés.
    """
    errors: dict[str, list[str]] = {}
    if not isinstance(overrides, dict):
        raise RuleValidationError({"_root": ["attendu dict racine"]})
    for rid, ov in overrides.items():
        rule = _REGISTRY.get(rid)
        if rule is None:
            errors[rid] = ["règle inconnue"]
            continue
        if not isinstance(ov, dict):
            errors[rid] = ["override doit être un dict"]
            continue
        # enabled
        if "enabled" in ov and not isinstance(ov["enabled"], bool):
            errors.setdefault(rid, []).append("enabled doit être un bool")
        # params
        params = ov.get("params")
        if params is None:
            continue
        if not isinstance(params, dict):
            errors.setdefault(rid, []).append("params doit être un dict")
            continue
        for pname, pval in params.items():
            schema = rule.params.get(pname)
            if schema is None:
                errors.setdefault(rid, []).append(f"paramètre inconnu : {pname}")
                continue
            err = _validate_value(schema, pval)
            if err:
                errors.setdefault(rid, []).append(f"{pname}: {err}")
    if errors:
        raise RuleValidationError(errors)
