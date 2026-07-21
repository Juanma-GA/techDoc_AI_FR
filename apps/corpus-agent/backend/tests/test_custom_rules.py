"""Unitaires du check checklist (`custom_rules`) — filtres d'activation et
résolution des placeholders `{nom}` (référentiel + BASL).

Isolé : on monkeypatch `load_rules` / `reference_column_values` pour ne jamais
toucher au `data/rules.json` réel ni à un classeur du disque.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.checks import custom_rules


def test_load_custom_rules_filters_disabled_and_pending(monkeypatch) -> None:
    monkeypatch.setattr(custom_rules, "load_rules", lambda: {
        "regles_personnalisees": [
            {"id": "a", "label": "A", "consigne": "règle active", "severity": "high"},
            {"id": "b", "label": "B", "consigne": "désactivée", "enabled": False},
            {"id": "c", "label": "C", "consigne": "en attente", "validated": False},
            {"id": "d", "label": "D", "consigne": "activée explicite", "enabled": True, "validated": True},
            {"id": "e", "label": "E", "consigne": "   "},  # consigne vide -> ignorée
        ]
    })
    ids = {r["id"] for r in custom_rules._load_custom_rules()}
    assert ids == {"a", "d"}  # b (disabled), c (pending), e (vide) exclues


def test_resolve_placeholders_reference_then_basl(monkeypatch) -> None:
    # Colonne inconnue des deux registres -> placeholder laissé tel quel ;
    # `script` (builtin référentiel) -> source "reference" ;
    # `rechange` (builtin BASL) -> source "BASL".
    monkeypatch.setattr(custom_rules, "reference_column_values",
                        lambda path, sheet, column, *a, **k: ["X100", "X200"])
    project = SimpleNamespace(
        reference_columns=None, basl_columns=None,
        reference_path="/ref.xlsx", basl_path="/basl.xlsx",
    )
    out = custom_rules._resolve_placeholders(
        "script {script} ; rechange {rechange} ; inconnu {zzz}", project,
    )
    assert "colonne reference « script » : X100, X200" in out
    assert "colonne BASL « rechange » : X100, X200" in out
    assert "{zzz}" in out  # non résolu, laissé littéral
