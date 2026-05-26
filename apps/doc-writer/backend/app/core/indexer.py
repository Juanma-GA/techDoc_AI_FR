"""Chunking + embeddings (Mistral) + recherche cosinus via numpy.

Stockage des vecteurs : `bytes` (numpy float32) dans la colonne
`document_chunks.embedding`. La similarité est calculée Python-side : pour un
POC local sur quelques milliers de chunks, c'est suffisant — pas besoin de
pgvector ou sqlite-vec.
"""

from __future__ import annotations

import uuid
from typing import Iterable, Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.mistral_client import MistralClient
from app.db.models import Document, DocumentChunk


CHUNK_SIZE_CHARS = 800 * 4   # ~800 tokens
CHUNK_OVERLAP_CHARS = 120 * 4
EMBED_BATCH = 32


def chunk_text(
    text: str,
    size: int = CHUNK_SIZE_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """Découpe sur double-newline si possible (sinon coupe nette à `size`)."""
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        slice_ = text[start:end]
        if end < n:
            last_nl = slice_.rfind("\n\n")
            if last_nl > size // 2:
                end = start + last_nl
                slice_ = text[start:end]
        cleaned = slice_.strip()
        if cleaned:
            chunks.append(cleaned)
        if end >= n:
            break
        start = max(0, end - overlap)
    return chunks


def _to_blob(vec: Iterable[float]) -> bytes:
    return np.asarray(list(vec), dtype=np.float32).tobytes()


def _from_blob(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)


def index_document(db: Session, document: Document, mistral: MistralClient) -> int:
    """(Re-)indexe le texte d'un Document. Retourne le nombre de chunks créés.

    Idempotent : supprime les anciens chunks avant de réindexer.
    """
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()

    chunks = chunk_text(document.extracted_text or "")
    if not chunks:
        document.chunk_count = 0
        db.commit()
        return 0

    all_vectors: list[list[float]] = []
    for i in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[i : i + EMBED_BATCH]
        all_vectors.extend(mistral.embed(batch))

    for idx, (text, vec) in enumerate(zip(chunks, all_vectors)):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=idx,
                text=text,
                embedding=_to_blob(vec),
            )
        )

    document.chunk_count = len(chunks)
    document.index_error = None
    db.commit()
    return len(chunks)


def search_similar(
    db: Session,
    doc_ids: Optional[list[uuid.UUID]],
    query: str,
    mistral: MistralClient,
    k: int = 8,
) -> list[dict]:
    """Cosine similarity Python-side. `doc_ids = None` ou `[]` → tous les docs."""
    if not query.strip():
        return []
    query_vec = np.asarray(mistral.embed([query])[0], dtype=np.float32)
    qn = float(np.linalg.norm(query_vec))
    if qn == 0:
        return []

    stmt = select(DocumentChunk)
    if doc_ids:
        stmt = stmt.where(DocumentChunk.document_id.in_(doc_ids))
    chunks = list(db.scalars(stmt))

    scored: list[tuple[float, DocumentChunk]] = []
    for c in chunks:
        vec = _from_blob(c.embedding)
        vn = float(np.linalg.norm(vec))
        if vn == 0:
            continue
        score = float(np.dot(query_vec, vec) / (qn * vn))
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)

    out: list[dict] = []
    for score, c in scored[:k]:
        doc = c.document
        out.append(
            {
                "chunk_id": str(c.id),
                "document_id": str(doc.id),
                "filename": doc.filename,
                "score": round(score, 3),
                "text": c.text,
            }
        )
    return out
