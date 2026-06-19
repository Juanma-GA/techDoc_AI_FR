"""Garde-fous des appels LLM (concurrence + budget).

Partage sur toute une analyse (et, cote appelant, sur un lot) : un semaphore
borne la concurrence, un compteur borne le nombre total d'appels Mistral. Au-dela
du cap, `run()` renvoie None (degradation gracieuse : l'appelant bascule le
finding en manuel « non analyse par budget »).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Optional, TypeVar

T = TypeVar("T")


class LlmBudget:
    def __init__(self, max_calls: int, concurrency: int = 4) -> None:
        self.max_calls = max_calls
        self.used = 0
        self._sem = asyncio.Semaphore(max(1, concurrency))

    def remaining(self) -> int:
        return max(0, self.max_calls - self.used)

    async def run(self, factory: Callable[[], Awaitable[T]]) -> Optional[T]:
        if self.used >= self.max_calls:
            return None
        self.used += 1
        async with self._sem:
            return await factory()
