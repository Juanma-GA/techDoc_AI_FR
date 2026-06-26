"""SHA-256 helpers + Jaccard similarity. Ported as-is from legacy."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_of_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def jaccard_similarity(a: str, b: str, shingle_size: int = 5) -> float:
    """Rough content similarity via word shingles. Fast, no deps."""
    if not a or not b:
        return 0.0
    wa = a.split()
    wb = b.split()
    if len(wa) < shingle_size or len(wb) < shingle_size:
        set_a, set_b = set(wa), set(wb)
    else:
        set_a = {" ".join(wa[i:i + shingle_size]) for i in range(len(wa) - shingle_size + 1)}
        set_b = {" ".join(wb[i:i + shingle_size]) for i in range(len(wb) - shingle_size + 1)}
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0
