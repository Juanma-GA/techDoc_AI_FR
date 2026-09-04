"""Garde-fou de budget des appels LLM de fiabilisation.

Porté de word-reviewer, adapté au pipeline **synchrone** de doc-reviewer
(`rules_engine.run_all` tourne déjà dans un thread via `asyncio.to_thread` ;
pas besoin de sémaphore de concurrence). Un compteur borne le nombre total
d'appels Mistral supplémentaires dépensés par la vérification adversariale sur
une analyse. Au-delà du plafond, `spend()` renvoie False et l'appelant garde le
finding tel quel (dégradation gracieuse : on ne bloque jamais l'analyse).
"""

from __future__ import annotations


class LlmBudget:
    def __init__(self, max_calls: int) -> None:
        self.max_calls = max(0, int(max_calls))
        self.used = 0

    def remaining(self) -> int:
        return max(0, self.max_calls - self.used)

    def spend(self) -> bool:
        """Consomme un appel du budget. False si le plafond est atteint."""
        if self.used >= self.max_calls:
            return False
        self.used += 1
        return True
