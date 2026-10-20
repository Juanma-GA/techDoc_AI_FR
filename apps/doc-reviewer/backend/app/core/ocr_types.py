from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OcrBox:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    confidence: float | None = None


@dataclass(frozen=True)
class OcrPageResult:
    text: str
    boxes: list[OcrBox]
    provider: str
    elapsed_ms: int
