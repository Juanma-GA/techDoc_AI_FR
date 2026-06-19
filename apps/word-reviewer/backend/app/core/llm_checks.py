"""Evaluation des regles `llm_nl` par Mistral + couches de fiabilisation.

Strategie (async) couvrant TOUT le document :
  1. on decoupe le document en **morceaux** de blocs (`_CHUNK`) ; pour CHAQUE
     morceau, un seul appel evalue **toutes** les regles `llm_nl` a la fois
     (couverture complete, peu d'appels) ;
  2. **repli de zone** : une regle ciblant une zone non reconnue est evaluee
     sur tout le corps (sinon elle ne s'appliquerait jamais) ;
  3. **couche 2 (confiance)** : un finding sous le seuil -> `info` « a verifier »
     (pas d'application auto) ;
  4. **couche 1 (verif adversariale)** : les findings au seuil sont soumis a un
     refuteur independant ; ne survivent que les non refutes ;
  5. **garde-fous** : concurrence + cap d'appels (`LlmBudget`).

Si Mistral n'est pas configure, renvoie `[]` (l'analyse deterministe reste OK).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.checks.raw import RawSuggestion
from app.core import verifier
from app.core.llm_budget import LlmBudget
from app.core.mistral_client import MistralClient, MistralError, _read_config, get_llm_enabled
from app.parsers.docx_parser import Block, ParsedDocx

log = logging.getLogger("word_reviewer.llm_checks")

_CHUNK = 12  # blocs evalues par appel
_DEFAULT_THRESHOLD = 0.6
_DEFAULT_MAX_CALLS = 400
_DEFAULT_CONCURRENCY = 4
_MAX_FIX_LEN = 600  # au-dela, on signale sans proposer (re-ecriture peu fiable)

_SYSTEM = (
    "Tu es un relecteur qualite documentaire aeronautique (manuels CMM), rigoureux "
    "et CONSERVATEUR. On te donne une liste de REGLES numerotees et des EXTRAITS "
    "numerotes (chacun avec sa zone). Pour CHAQUE couple (regle r, extrait b) ou "
    "l'extrait viole REELLEMENT la regle, renvoie une entree. Ne signale rien si "
    "l'extrait est conforme ou hors sujet pour la regle (zone differente, type de "
    "contenu non concerne). Si une correction concrete est possible, `proposed` = "
    "l'extrait corrige COMPLET (sans guillemets) ; sinon `proposed` = \"\". "
    "Reponds uniquement en JSON : {\"violations\": [{\"r\": <int>, \"b\": <int>, "
    "\"confidence\": 0.0-1.0, \"reason\": \"...\", \"proposed\": \"...\"}]}."
)


def _cfg_float(db: Session, key: str, default: float) -> float:
    try:
        raw = _read_config(db, key, "")
        return float(raw) if raw else default
    except (ValueError, TypeError):
        return default


def _cfg_int(db: Session, key: str, default: int) -> int:
    try:
        raw = _read_config(db, key, "")
        return int(raw) if raw else default
    except (ValueError, TypeError):
        return default


def _parse_violations(text: str) -> list[dict[str, Any]]:
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        obj = json.loads(text[start:end])
        viol = obj.get("violations", [])
        return viol if isinstance(viol, list) else []
    except (ValueError, json.JSONDecodeError, TypeError):
        return []


def _applies(rule: dict[str, Any], block: Block) -> bool:
    """La regle (apres repli) s'applique-t-elle au bloc ?"""
    zone = rule.get("_zone_eff") or ""
    if not zone:
        return True
    return block.semantic_zone == zone or block.zone == zone


async def _eval_chunk(
    client: MistralClient, rules: list[dict[str, Any]], chunk: list[Block], budget: LlmBudget
) -> list[tuple[RawSuggestion, str, str]]:
    rules_txt = "\n".join(
        f"[{ri}] {r.get('message') or r.get('title') or r.get('name') or r.get('code')}"
        for ri, r in enumerate(rules)
    )
    blocks_txt = "\n".join(
        f"[{bi}] ({b.semantic_zone or b.zone}) {b.text[:_MAX_FIX_LEN]}" for bi, b in enumerate(chunk)
    )
    user = f"REGLES:\n{rules_txt}\n\nEXTRAITS:\n{blocks_txt}"

    async def _call() -> str:
        return await client.chat(
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
            temperature=0.1,
        )

    out = await budget.run(_call)
    if not out:
        return []
    findings: list[tuple[RawSuggestion, str, str]] = []
    for v in _parse_violations(out):
        try:
            ri = int(v.get("r"))
            bi = int(v.get("b"))
        except (TypeError, ValueError):
            continue
        if not (0 <= ri < len(rules) and 0 <= bi < len(chunk)):
            continue
        rule = rules[ri]
        block = chunk[bi]
        if not _applies(rule, block):
            continue
        conf = float(v.get("confidence", 0.5)) if isinstance(v.get("confidence"), (int, float)) else 0.5
        reason = str(v.get("reason") or rule.get("message") or rule.get("code"))
        proposed = str(v.get("proposed") or "").strip()
        corrective = bool(proposed) and proposed != block.text and len(block.text) <= _MAX_FIX_LEN
        raw = RawSuggestion(
            rule_kind=str(rule.get("rule_kind", "custom")),
            rule_code=str(rule["code"]),
            severity=str(rule.get("severity") or "warning"),
            message=reason,
            original=block.text if corrective else block.text[:160],
            proposed=proposed if corrective else "",
            target_id=block.target_id,
            block_index=block.index,
            zone=block.zone,
            semantic_zone=block.semantic_zone or "",
            char_start=0,
            char_end=len(block.text) if corrective else 0,
            confidence=conf,
            rule_id=rule.get("rule_id"),
        )
        findings.append((raw, str(rule.get("message") or rule.get("code")), block.text))
    return findings


async def _post_process(
    client: MistralClient,
    findings: list[tuple[RawSuggestion, str, str]],
    threshold: float,
    budget: LlmBudget,
) -> list[RawSuggestion]:
    survivors: list[RawSuggestion] = []
    for raw, rule_text, excerpt in findings:
        if raw.confidence is not None and raw.confidence < threshold:
            # Couche 2 : confiance basse -> a verifier (pas d'assertion / d'application).
            raw.severity = "info"
            raw.message = f"[A verifier] {raw.message}"
            raw.proposed = ""
            raw.char_start = raw.char_end = 0
            survivors.append(raw)
            continue
        # Couche 1 : verification adversariale reservee aux findings `error`
        # (haut risque). Les warning/info au-dessus du seuil sont conserves :
        # la confiance a deja fait le tri ; sur-filtrer viderait l'analyse.
        if raw.severity == "error":
            try:
                keep = await verifier.survives(client, raw, rule_text, excerpt, budget)
            except Exception as exc:  # noqa: BLE001
                log.warning("verification failed, keeping finding: %s", exc)
                keep = True
            if not keep:
                continue
        survivors.append(raw)
    return survivors


async def run_llm_iter(db: Session, parsed: ParsedDocx, rules: list[dict[str, Any]]):
    """Variante **incrementale** : yield des evenements de progression puis le
    resultat. Permet a l'appelant (SSE) d'afficher l'avancement en direct.

    Evenements : {"type":"start","total":N} -> {"type":"progress","done":k,
    "total":N}* -> {"type":"result","survivors":[...]}.
    """
    if not get_llm_enabled(db):
        yield {"type": "result", "survivors": []}
        return
    llm_rules = [r for r in rules if (r.get("kind") or "").lower() == "llm_nl"]
    if not llm_rules:
        yield {"type": "result", "survivors": []}
        return
    try:
        client = MistralClient.from_db(db)
    except MistralError:
        log.info("Mistral non configure : passe LLM ignoree.")
        yield {"type": "result", "survivors": []}
        return

    blocks = [b for b in parsed.blocks if b.text.strip()]
    if not blocks:
        yield {"type": "result", "survivors": []}
        return

    # Repli de zone : une zone cible non reconnue -> evaluation sur tout le corps.
    zones_present = {b.semantic_zone for b in blocks} | {b.zone for b in blocks}
    for r in llm_rules:
        tz = (r.get("target_zone") or "").strip()
        r["_zone_eff"] = tz if tz in zones_present else ""

    threshold = _cfg_float(db, "LLM_CONFIDENCE_THRESHOLD", _DEFAULT_THRESHOLD)
    max_calls = _cfg_int(db, "LLM_MAX_CALLS", _DEFAULT_MAX_CALLS)
    concurrency = _cfg_int(db, "LLM_CONCURRENCY", _DEFAULT_CONCURRENCY)
    budget = LlmBudget(max_calls, concurrency)

    chunks = [blocks[i:i + _CHUNK] for i in range(0, len(blocks), _CHUNK)]
    total = len(chunks)
    yield {"type": "start", "total": total}

    # Le semaphore du budget borne la concurrence reelle ; on cree toutes les
    # taches et on les recolte au fil de l'eau pour reporter la progression.
    tasks = [asyncio.ensure_future(_eval_chunk(client, llm_rules, ch, budget)) for ch in chunks]
    findings: list[tuple[RawSuggestion, str, str]] = []
    done = 0
    for fut in asyncio.as_completed(tasks):
        sub = await fut
        findings.extend(sub)
        done += 1
        yield {"type": "progress", "done": done, "total": total}

    survivors = await _post_process(client, findings, threshold, budget)
    yield {"type": "result", "survivors": survivors}


async def run_llm(db: Session, parsed: ParsedDocx, rules: list[dict[str, Any]]) -> list[RawSuggestion]:
    survivors: list[RawSuggestion] = []
    async for ev in run_llm_iter(db, parsed, rules):
        if ev["type"] == "result":
            survivors = ev["survivors"]
    return survivors
