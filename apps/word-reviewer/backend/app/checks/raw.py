"""Type de transport partage entre les checks et le moteur.

`RawSuggestion` est l'equivalent docx (par **bloc**, pas par bbox) de la
suggestion brute du pdf-reviewer. `rules_engine.materialize()` la convertit en
ligne ORM `Suggestion`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass
class RawSuggestion:
    rule_kind: str  # "standard" | "custom"
    rule_code: str
    severity: str
    message: str
    original: str
    proposed: str
    target_id: str = ""
    block_index: int = 0
    zone: str = "body"
    semantic_zone: str = ""
    char_start: int = 0
    char_end: int = 0
    confidence: Optional[float] = None
    rule_id: Optional[uuid.UUID] = None

    def dedupe_key(self) -> tuple:
        return (
            self.rule_code,
            self.target_id,
            self.original,
            self.char_start,
            self.message,
        )
