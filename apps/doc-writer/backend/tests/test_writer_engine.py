"""writer_engine.build_messages — comportement SANS source (génération libre).

Quand aucune source n'est sélectionnée (scope vide), on ne fait PAS de RAG et on
rédige depuis le seul brief : pas de bloc "Extraits pertinents", pas de citations,
prompt système "freeform" (sans contrainte d'extraits).
"""

from __future__ import annotations

from app.core import writer_engine as we
from app.db.models import Session as SessionRow


def _session(**kw) -> SessionRow:
    defaults = dict(
        title="",
        scope_doc_ids="[]",
        lang="fr",
        output_format="markdown",
        length="medium",
        tone="professional",
        style_doc_id=None,
        template_doc_id=None,
    )
    defaults.update(kw)
    return SessionRow(**defaults)


def test_no_scope_is_freeform_no_rag() -> None:
    session = _session(scope_doc_ids="[]")
    # mistral=None et db=None : la branche freeform ne doit ni faire de RAG ni
    # toucher la base (pas de source -> rien à charger).
    messages, citations = we.build_messages(
        None, session, "Rédige une note interne sur la sécurité incendie.",
        mistral=None,
    )

    assert citations == []
    system = messages[0]["content"]
    # Prompt freeform (marqueur distinctif) et PAS la contrainte de grounding
    # (le prompt RAG dit "n'est pas dans les extraits, indique-le").
    assert "Aucun document source" in system
    assert "pas dans les extraits" not in system.lower()
    assert "cites systématiquement tes sources" not in system.lower()

    user = messages[-1]["content"]
    assert "Extraits pertinents" not in user
    assert "Brief : Rédige une note interne sur la sécurité incendie." in user


def test_empty_string_scope_is_freeform() -> None:
    # scope_doc_ids peut être une chaîne vide (server_default) : même traitement.
    session = _session(scope_doc_ids="")
    messages, citations = we.build_messages(None, session, "Plan de formation.", mistral=None)
    assert citations == []
    assert "Aucun document source" in messages[0]["content"]


def test_freeform_respects_output_options() -> None:
    # Les options (format/longueur/ton) restent appliquées en l'absence de source.
    session = _session(scope_doc_ids="[]", output_format="faq", length="long")
    messages, _ = we.build_messages(None, session, "Sujet libre.", mistral=None)
    system = messages[0]["content"]
    assert "FAQ" in system
    assert "LONGUEUR" in system


def test_freeform_lang_directive_en() -> None:
    session = _session(scope_doc_ids="[]", lang="en")
    messages, _ = we.build_messages(None, session, "Free topic.", mistral=None)
    assert "No source document is provided" in messages[0]["content"]
    # Directive de langue EN présente en tête du user message.
    assert messages[-1]["content"].startswith("LANGUAGE DIRECTIVE")
