"""Extraction structuree : texte OCR -> N lignes suivant les colonnes/regles.

Construit un prompt a partir du markdown OCR et des colonnes d'une table
(cle + type + regle), demande au modele chat un tableau JSON de lignes, puis
parse/coerce le resultat. Aucune dependance LangChain / SDK Mistral (regle #6).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.mistral_client import MistralClient

logger = logging.getLogger(__name__)


_SYSTEM = (
    "Tu es un moteur d'extraction de donnees. A partir du texte d'un document "
    "(issu d'un OCR, en markdown), tu remplis un tableau. Tu reponds "
    "EXCLUSIVEMENT par un tableau JSON (une liste d'objets), sans texte autour, "
    "sans bloc de code. Chaque objet est une ligne du tableau ; ses cles sont "
    "EXACTEMENT les cles de colonnes fournies. Si le document contient plusieurs "
    "elements (lignes d'articles, entrees...), produis une ligne par element. "
    "Si une valeur est absente, mets une chaine vide. N'invente aucune donnee."
)


def _columns_brief(columns: list[dict[str, Any]]) -> str:
    lines = []
    for c in columns:
        key = c.get("key", "")
        ctype = c.get("type", "text")
        rule = (c.get("rule") or "").strip()
        label = (c.get("label") or "").strip()
        desc = rule or label or key
        lines.append(f'- "{key}" (type {ctype}) : {desc}')
    return "\n".join(lines)


def build_messages(columns: list[dict[str, Any]], ocr_text: str) -> list[dict[str, str]]:
    keys = [c.get("key", "") for c in columns]
    user = (
        "Colonnes a remplir (cle, type, regle) :\n"
        f"{_columns_brief(columns)}\n\n"
        f"Cles JSON attendues, dans cet ordre : {json.dumps(keys, ensure_ascii=False)}\n\n"
        "Texte du document (OCR) :\n"
        "-----\n"
        f"{ocr_text}\n"
        "-----\n\n"
        "Reponds par le tableau JSON des lignes."
    )
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user},
    ]


def _strip_json(raw: str) -> str:
    """Retire un eventuel bloc ```json ... ``` et isole le premier tableau."""
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _coerce(value: Any, ctype: str) -> Any:
    if value is None:
        return ""
    if ctype == "number":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        s = str(value).strip().replace(" ", "").replace(",", ".")
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        return float(m.group(0)) if m else str(value).strip()
    if ctype == "bool":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "vrai", "yes", "oui", "x"}
    return str(value).strip()


def parse_rows(raw: str, columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse la reponse LLM en lignes coercees ; ne garde que les cles connues."""
    try:
        data = json.loads(_strip_json(raw))
    except (json.JSONDecodeError, ValueError):
        logger.warning("extraction: reponse LLM non parsable en JSON")
        return []
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []

    types = {c.get("key", ""): c.get("type", "text") for c in columns}
    keys = list(types.keys())
    rows: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        row = {k: _coerce(item.get(k, ""), types.get(k, "text")) for k in keys}
        if any(str(v).strip() for v in row.values()):
            rows.append(row)
    return rows


def extract_rows(
    client: MistralClient, columns: list[dict[str, Any]], ocr_text: str
) -> list[dict[str, Any]]:
    """OCR text -> lignes. Renvoie [] si pas de colonnes ou texte vide."""
    if not columns or not ocr_text.strip():
        return []
    raw = client.chat(build_messages(columns, ocr_text), temperature=0.0)
    return parse_rows(raw, columns)
