"""Chunking + embeddings (Mistral) + cosine search via numpy.
Ported from legacy with UUID-aware filters."""

from __future__ import annotations

import uuid

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.mistral_client import MistralClient
from app.db.models import DocumentChunk, File, FileVersion


CHUNK_SIZE_CHARS = 800 * 4  # ~800 tokens
CHUNK_OVERLAP_CHARS = 120 * 4


def chunk_text(text: str, size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    text = text.strip()
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
        chunks.append(slice_.strip())
        if end >= n:
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c]


def embeddings_to_bytes(vec: list[float]) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def bytes_to_embedding(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)


def index_file_version(db: Session, version: FileVersion, mistral: MistralClient) -> int:
    """(Re)index a FileVersion's text into DocumentChunks. Returns chunks count."""
    db.query(DocumentChunk).filter(DocumentChunk.file_version_id == version.id).delete()

    chunks = chunk_text(version.extracted_text or "")
    if not chunks:
        db.commit()
        return 0

    batch_size = 32
    all_vectors: list[list[float]] = []
    for i in range(0, len(chunks), batch_size):
        all_vectors.extend(mistral.embed(chunks[i:i + batch_size]))

    for idx, (text, vec) in enumerate(zip(chunks, all_vectors)):
        db.add(DocumentChunk(
            file_version_id=version.id,
            chunk_index=idx,
            text=text,
            embedding=embeddings_to_bytes(vec),
        ))
    db.commit()
    return len(chunks)


def search_similar(
    db: Session,
    project_ids: list[uuid.UUID] | None,
    query: str,
    mistral: MistralClient,
    k: int = 6,
) -> list[dict]:
    """`project_ids = None` ou `[]` → recherche sur tous les projets.
    `[uuid]` → un projet. `[uuid1, uuid2, …]` → subset multi-projets."""
    query_vec = np.asarray(mistral.embed([query])[0], dtype=np.float32)
    qn = float(np.linalg.norm(query_vec))
    if qn == 0:
        return []

    stmt = (
        select(DocumentChunk)
        .join(FileVersion, DocumentChunk.file_version_id == FileVersion.id)
        .join(File, FileVersion.file_id == File.id)
    )
    if project_ids:
        stmt = stmt.where(File.project_id.in_(project_ids))
    chunks = list(db.scalars(stmt))

    scored: list[tuple[float, DocumentChunk]] = []
    for c in chunks:
        if not c.embedding:
            continue
        vec = bytes_to_embedding(c.embedding)
        vn = float(np.linalg.norm(vec))
        if vn == 0:
            continue
        score = float(np.dot(query_vec, vec) / (qn * vn))
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[dict] = []
    for score, c in scored[:k]:
        v = c.file_version
        out.append({
            "chunk_id": str(c.id),
            "file_version_id": str(v.id),
            "filename": v.filename,
            "score": round(score, 3),
            "text": c.text,
        })
    return out
