"""Checks bases sur le suivi de modifications Word (kind `revision_check`).

S'appuient sur `Block.revised` / `Block.revision_kind` et `parsed.revisions`
renseignes par le parser. Sous-checks geometriques (R/U pair-impair) hors scope :
ils restent en `manual`.
"""

from __future__ import annotations

from typing import Any

from app.checks.raw import RawSuggestion
from app.parsers.docx_parser import ParsedDocx


def run(parsed: ParsedDocx, rule: dict[str, Any]) -> list[RawSuggestion]:
    require = (rule.get("metadata") or {}).get("require", "bar")
    out: list[RawSuggestion] = []
    if require == "bar":
        # Tout bloc insere/supprime (ins/del) doit aussi porter une barre de
        # revision (pBdr). On signale les blocs modifies sans barre.
        for block in parsed.blocks:
            if block.revision_kind in {"ins", "del"} and block.revision_kind != "bar":
                has_bar = any(
                    b.target_id == block.target_id and b.revision_kind == "bar"
                    for b in parsed.blocks
                )
                if not has_bar:
                    out.append(
                        RawSuggestion(
                            rule_kind=str(rule.get("rule_kind", "standard")),
                            rule_code=str(rule["code"]),
                            severity=str(rule.get("severity") or "warning"),
                            message=str(rule.get("message") or rule["code"]),
                            original=block.text[:160],
                            proposed="",
                            target_id=block.target_id,
                            block_index=block.index,
                            zone=block.zone,
                            semantic_zone=block.semantic_zone or "",
                        )
                    )
    return out
