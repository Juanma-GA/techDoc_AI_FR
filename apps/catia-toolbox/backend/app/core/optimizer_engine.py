"""Moteur d'optimisation : baseline deterministe + plan LLM (Mistral SSE).

- `build_baseline_suggestions` : suggestions deterministes issues des metriques
  (regroupement par type, normalisation de noms). Disponibles meme sans Mistral.
- `build_messages` / `stream_plan` : appel Mistral en streaming. Le prompt
  produit un flux narratif puis un bloc JSON final `{"suggestions": [...]}`.
- `parse_suggestions_from_text` : extrait le bloc JSON du flux accumule.

Le moteur ne deplace JAMAIS de fichier : il ne produit que des suggestions.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Any, Optional

from app.core.mistral_client import MistralClient
from app.core.parser import ParsedNode


_MAX_SAMPLE_PATHS = 200
_VALID_ACTIONS = {"move", "rename", "group", "keep"}

SYSTEM_PROMPT = (
    "Tu es un expert en organisation d'arborescences de fichiers CATIA exportees. "
    "On te fournit (a) des metriques calculees sur l'arborescence existante "
    "(profondeur, fan-out, incoherences de nommage, doublons, dispersion "
    "d'extensions) et (b) un echantillon de chemins relatifs.\n\n"
    "Tu proposes une taxonomie cible reorganisee. Pour chaque element a "
    "deplacer, renommer ou regrouper, tu produis un objet "
    "{old_path, new_path, action, rationale, confidence}.\n"
    "- action : move | rename | group | keep\n"
    "- confidence : elevee | moyenne | faible\n"
    "- old_path et new_path sont des chemins relatifs en slash avant (/).\n\n"
    "Contraintes STRICTES :\n"
    "- Tu ne deplaces JAMAIS de fichier toi-meme : tu produis un PLAN.\n"
    "- Ne perds aucun fichier ; conserve les extensions.\n"
    "- Regroupe par type / famille fonctionnelle ; limite la profondeur cible.\n"
    "- Aucune suppression : pas d'action 'delete'.\n\n"
    "Reponds d'abord par une courte analyse narrative en francais (3-6 lignes), "
    "puis termine OBLIGATOIREMENT par un bloc JSON : "
    '```json\n{"suggestions": [ ... ]}\n```'
)


def build_baseline_suggestions(
    nodes: list[ParsedNode],
    metrics: dict,
    config: dict,
) -> list[dict]:
    """Suggestions deterministes — utiles meme si Mistral est indisponible."""
    suggestions: list[dict] = []
    scattered_exts = {row["ext"] for row in metrics.get("scattered_extensions", [])}

    for n in nodes:
        if n.kind != "file":
            continue
        # 1. Regroupement par type pour les extensions dispersees.
        if n.ext and n.ext in scattered_exts:
            new_name = _normalize_name(n.name)
            new_path = f"by-type/{n.ext}/{new_name}"
            if new_path != n.rel_path:
                suggestions.append(
                    {
                        "old_path": n.rel_path,
                        "new_path": new_path,
                        "action": "group",
                        "rationale": f"Extension .{n.ext} dispersee : regroupement par type.",
                        "confidence": "moyenne",
                        "source": "baseline",
                        "node_rel_path": n.rel_path,
                    }
                )
                continue
        # 2. Normalisation des noms a espaces / majuscules.
        normalized = _normalize_name(n.name)
        if normalized != n.name:
            parent = n.parent_path + "/" if n.parent_path else ""
            suggestions.append(
                {
                    "old_path": n.rel_path,
                    "new_path": f"{parent}{normalized}",
                    "action": "rename",
                    "rationale": "Normalisation du nom (espaces / casse) en kebab-case.",
                    "confidence": "faible",
                    "source": "baseline",
                    "node_rel_path": n.rel_path,
                }
            )

    return suggestions


def _normalize_name(name: str) -> str:
    stem, dot, ext = name.rpartition(".")
    base = stem if dot else name
    norm = re.sub(r"[\s_]+", "-", base.strip()).lower()
    norm = re.sub(r"-{2,}", "-", norm).strip("-") or base.lower()
    return f"{norm}.{ext.lower()}" if dot else norm


def build_messages(metrics: dict, sample_paths: list[str], config: dict) -> list[dict]:
    user = {
        "config": config,
        "metrics": metrics,
        "sample_paths": sample_paths[:_MAX_SAMPLE_PATHS],
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Analyse cette arborescence et propose un plan de reorganisation.\n\n"
                + json.dumps(user, ensure_ascii=False, indent=2)
            ),
        },
    ]


async def stream_plan(
    mistral: MistralClient,
    metrics: dict,
    sample_paths: list[str],
    config: dict,
    *,
    temperature: float = 0.2,
) -> AsyncIterator[str]:
    messages = build_messages(metrics, sample_paths, config)
    async for delta in mistral.chat_stream(messages, temperature=temperature):
        yield delta


def parse_suggestions_from_text(text: str) -> list[dict]:
    """Extrait la liste `suggestions` du flux accumule (bloc JSON final)."""
    payload = _extract_json_object(text)
    if not payload:
        return []
    raw = payload.get("suggestions")
    if not isinstance(raw, list):
        return []

    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        old = str(item.get("old_path", "")).strip()
        new = str(item.get("new_path", "")).strip()
        action = str(item.get("action", "move")).strip().lower()
        if action not in _VALID_ACTIONS:
            action = "move"
        if not old or not new:
            continue
        out.append(
            {
                "old_path": old,
                "new_path": new,
                "action": action,
                "rationale": str(item.get("rationale", "")).strip(),
                "confidence": _norm_confidence(item.get("confidence")),
                "source": "llm",
                "node_rel_path": old,
            }
        )
    return out


def _norm_confidence(v: object) -> str:
    s = str(v or "").strip().lower()
    return s if s in ("elevee", "moyenne", "faible") else "moyenne"


def _extract_json_object(text: str) -> Optional[dict]:
    # 1. Bloc ```json ... ``` (le dernier l'emporte).
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    for block in reversed(blocks):
        obj = _try_load(block)
        if obj is not None:
            return obj
    # 2. Fallback : dernier objet `{...}` contenant "suggestions".
    for match in reversed(list(re.finditer(r"\{.*\}", text, flags=re.DOTALL))):
        obj = _try_load(match.group(0))
        if obj is not None and "suggestions" in obj:
            return obj
    return None


def _try_load(s: str) -> Optional[dict]:
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None
