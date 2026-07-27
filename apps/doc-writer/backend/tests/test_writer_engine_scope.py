"""writer_engine : selection "document entier" vs RAG top-k pour le scope.

Couvre la decision de `_scope_full_texts` (sans Mistral) : une source courte
en scope est passee ENTIERE au modele ; au-dela du budget, on retombe sur le
RAG (la fonction renvoie []).
"""

from __future__ import annotations

import uuid


def _add_source_doc(text: str) -> uuid.UUID:
    from app.db.models import Document
    from app.db.session import SessionLocal

    doc_id = uuid.uuid4()
    db = SessionLocal()
    try:
        db.add(
            Document(
                id=doc_id,
                filename=f"cv_{doc_id.hex[:8]}.pdf",
                sha256=doc_id.hex,  # unique
                storage_path=f"/tmp/{doc_id.hex}.pdf",
                extracted_text=text,
                kind="source",
            )
        )
        db.commit()
    finally:
        db.close()
    return doc_id


def test_scope_full_texts_returns_full_text_under_budget():
    from app.core.writer_engine import _scope_full_texts
    from app.db.session import SessionLocal

    doc_id = _add_source_doc("Anglais B2. Espagnol courant. 2018-2021 mission X.")
    db = SessionLocal()
    try:
        out = _scope_full_texts(db, [doc_id])
    finally:
        db.close()

    assert len(out) == 1
    assert "Anglais B2" in out[0][1]


def test_scope_full_texts_falls_back_to_rag_when_too_long():
    from app.core.writer_engine import _FULL_SOURCE_CHAR_BUDGET, _scope_full_texts
    from app.db.session import SessionLocal

    doc_id = _add_source_doc("x" * (_FULL_SOURCE_CHAR_BUDGET + 1))
    db = SessionLocal()
    try:
        out = _scope_full_texts(db, [doc_id])
    finally:
        db.close()

    assert out == []  # trop long -> on garde le RAG top-k


def test_scope_full_texts_skips_empty_text():
    from app.core.writer_engine import _scope_full_texts
    from app.db.session import SessionLocal

    doc_id = _add_source_doc("   ")  # texte vide apres strip
    db = SessionLocal()
    try:
        out = _scope_full_texts(db, [doc_id])
    finally:
        db.close()

    assert out == []
