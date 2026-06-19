"""Tests du registry des règles — phase 1+2 du refactor.

Couvre :
- enregistrement, résolution legacy / sparse, sérialisation catalogue
- validation des overrides sparse (types, contraintes, regex compile, IDs inconnus)
- détection des capacités runtime + `rule_is_runnable`
- comportement de la pilot `illustration` au travers du registry (toggle,
  override de paramètres, désactivation par capabilities).
"""

from __future__ import annotations

import pytest

# Importer illustration enregistre ses 5 règles dans le registry.
from app.checks.illustration import (
    COHERENCE_REPERES, CONFORMITE_VISUELLE, DIMENSIONS, FORMAT_REPERAGE,
    TAILLE_TOTALE,
)
from app.core.rules_registry import (
    Example, ParamSchema, Rule, RuleValidationError, _REGISTRY,
    all_rules, detect_capabilities, get_rule, register,
    resolve_rules, rule_is_runnable, to_catalog, validate_sparse_overrides,
)


# ---------------------------------------------------------------------------
# Registry & resolution
# ---------------------------------------------------------------------------

def test_illustration_rules_are_registered() -> None:
    """Les 5 règles `illustrations.*` sont enregistrées au moment de l'import."""
    ids = {r.id for r in all_rules()}
    assert "illustrations.format_reperage" in ids
    assert "illustrations.dimensions" in ids
    assert "illustrations.taille_totale" in ids
    assert "illustrations.coherence_reperes" in ids
    assert "illustrations.conformite_visuelle" in ids


def test_resolve_legacy_empty_yields_defaults() -> None:
    """Un legacy vide ⇒ chaque règle prend ses défauts via le resolver."""
    resolved = resolve_rules({}, legacy=True)
    fmt = resolved[FORMAT_REPERAGE.id]
    assert fmt.enabled is True
    assert fmt.params["pattern"] == r"Rep\d+\(Fig\d+\)"
    dim = resolved[DIMENSIONS.id]
    assert dim.params == {"min_px": 900, "max_px": 1200}
    siz = resolved[TAILLE_TOTALE.id]
    assert siz.params == {"max_ko": 400}
    coh = resolved[COHERENCE_REPERES.id]
    assert coh.enabled is True  # défaut legacy
    vis = resolved[CONFORMITE_VISUELLE.id]
    # Catalogue v5 : le default des questions vision est désormais une liste
    # non-vide (les 5+ questions standard sont la spec métier baked-in).
    # Donc legacy vide ⇒ defaults appliqués ⇒ enabled.
    assert vis.enabled is True
    assert len(vis.params["questions"]) >= 5


def test_resolve_legacy_with_overrides() -> None:
    """Le legacy resolver lit les bonnes clés."""
    legacy = {
        "illustrations": {
            "regex_reperage": r"FOO\d+",
            "largeur_min_px": 800,
            "largeur_max_px": 1500,
            "taille_totale_max_ko": 200,
            "coherence_reperes": False,
            "conformite_visuelle": ["Question 1", "Question 2"],
        }
    }
    resolved = resolve_rules(legacy, legacy=True)
    assert resolved[FORMAT_REPERAGE.id].params["pattern"] == r"FOO\d+"
    assert resolved[DIMENSIONS.id].params == {"min_px": 800, "max_px": 1500}
    assert resolved[TAILLE_TOTALE.id].params == {"max_ko": 200}
    assert resolved[COHERENCE_REPERES.id].enabled is False
    assert resolved[CONFORMITE_VISUELLE.id].enabled is True
    assert resolved[CONFORMITE_VISUELLE.id].params["questions"] == ["Question 1", "Question 2"]


def test_resolve_sparse_overrides() -> None:
    """Mode sparse : `{rule_id: {enabled, params}}` avec params absents = défauts."""
    overrides = {
        DIMENSIONS.id: {"enabled": False, "params": {"min_px": 500}},
        FORMAT_REPERAGE.id: {"params": {"pattern": r"X\d+\(Y\d+\)"}},
    }
    resolved = resolve_rules(overrides, legacy=False)
    dim = resolved[DIMENSIONS.id]
    assert dim.enabled is False
    assert dim.params["min_px"] == 500
    assert dim.params["max_px"] == 1200  # défaut conservé
    fmt = resolved[FORMAT_REPERAGE.id]
    assert fmt.enabled is True  # défaut enabled_default
    assert fmt.params["pattern"] == r"X\d+\(Y\d+\)"


def test_legacy_resolver_robust_to_garbage() -> None:
    """Un legacy mal formé (clé manquante / type faux) ne crashe pas — défauts."""
    resolved = resolve_rules({"illustrations": "not a dict"}, legacy=True)
    assert resolved[DIMENSIONS.id].params == {"min_px": 900, "max_px": 1200}


# ---------------------------------------------------------------------------
# Catalogue + (de-)sérialisation
# ---------------------------------------------------------------------------

def test_to_catalog_exposes_metadata_only() -> None:
    """Le catalogue ne fuite pas les callables (legacy_resolver, validator)."""
    cat = to_catalog()
    fmt = next(c for c in cat if c["id"] == FORMAT_REPERAGE.id)
    assert "legacy_resolver" not in fmt
    assert fmt["family"] == "illustrations"
    assert fmt["severity"] == "low"
    assert fmt["params"]["pattern"]["type"] == "regex"
    assert any(e["valid"] is False for e in fmt["examples"])  # au moins 1 contre-exemple


# ---------------------------------------------------------------------------
# Validation des overrides sparse
# ---------------------------------------------------------------------------

def test_validate_accepts_well_formed_overrides() -> None:
    validate_sparse_overrides({
        DIMENSIONS.id: {"enabled": True, "params": {"min_px": 1000, "max_px": 1500}},
        COHERENCE_REPERES.id: {"enabled": False},
    })


def test_validate_rejects_unknown_rule_id() -> None:
    with pytest.raises(RuleValidationError) as exc:
        validate_sparse_overrides({"foo.bar": {}})
    assert "foo.bar" in exc.value.errors


def test_validate_rejects_enabled_wrong_type() -> None:
    with pytest.raises(RuleValidationError) as exc:
        validate_sparse_overrides({DIMENSIONS.id: {"enabled": "oui"}})
    assert DIMENSIONS.id in exc.value.errors


def test_validate_rejects_int_out_of_constraints() -> None:
    with pytest.raises(RuleValidationError) as exc:
        validate_sparse_overrides({DIMENSIONS.id: {"params": {"min_px": -10}}})
    assert any("min_px" in e for e in exc.value.errors[DIMENSIONS.id])


def test_validate_rejects_invalid_regex() -> None:
    with pytest.raises(RuleValidationError) as exc:
        validate_sparse_overrides({FORMAT_REPERAGE.id: {"params": {"pattern": "["}}})
    assert any("regex" in e for e in exc.value.errors[FORMAT_REPERAGE.id])


def test_validate_rejects_unknown_param() -> None:
    with pytest.raises(RuleValidationError) as exc:
        validate_sparse_overrides({DIMENSIONS.id: {"params": {"foo": 1}}})
    assert any("foo" in e for e in exc.value.errors[DIMENSIONS.id])


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

def test_capabilities_without_mistral() -> None:
    caps = detect_capabilities(None)
    assert "mistral_vision" not in caps
    assert "parser_xlsm" in caps


def test_capabilities_with_full_mistral() -> None:
    caps = detect_capabilities({
        "api_key": "sk-test",
        "chat_model": "mistral-small-latest",
        "vision_model": "mistral-medium-latest",
        "embed_model": "mistral-embed",
    })
    assert {"mistral_chat", "mistral_vision", "mistral_embeddings"} <= caps


def test_rule_is_runnable_blocks_vision_when_unavailable() -> None:
    """Une règle requires=('mistral_vision',) n'est pas runnable sans vision."""
    caps_no_vision = {"parser_xlsm", "mistral_chat"}
    assert rule_is_runnable(COHERENCE_REPERES, caps_no_vision) is False  # type: ignore[arg-type]
    assert rule_is_runnable(FORMAT_REPERAGE, caps_no_vision) is True  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Garde-fous registry
# ---------------------------------------------------------------------------

def test_duplicate_id_raises() -> None:
    """Une seconde déclaration d'un même id est rejetée à l'enregistrement."""
    with pytest.raises(ValueError):
        register(Rule(
            id=FORMAT_REPERAGE.id,
            family="x", name_key="x", description_key="x",
        ))
