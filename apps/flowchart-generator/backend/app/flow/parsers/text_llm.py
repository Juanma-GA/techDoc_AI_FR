"""Texte libre -> FlowGraph.

Avec LLM : Mistral produit un JSON strict conforme au schema FlowGraph.
Sans LLM (interrupteur OFF, cle absente, erreur reseau, JSON invalide) :
repli deterministe ligne a ligne, jamais d'erreur 5xx.
"""

from __future__ import annotations

import json
import re
from itertools import pairwise

import structlog
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.mistral_client import MistralClient, MistralError, get_llm_enabled
from app.flow.model import FlowGraph, slug_id
from app.flow.parsers.json_dsl import graph_from_dict

log = structlog.get_logger("flowchart_generator.parse_text")

SYSTEM_PROMPT = """Tu es un expert en maintenance industrielle et en redaction de procedures de depannage
(logigrammes de diagnostic ISO 5807, isolation de panne S1000D,
manuels de reparation vehicule / systeme complexe).
Transforme la description (symptome, contexte, savoir-faire) en logigramme de depannage.
Reponds UNIQUEMENT par un objet JSON :
{"title": str, "system": str, "fault_code": str, "direction": "TB",
 "lanes": [{"id": str, "label": str}],
 "nodes": [{"id": str, "label": str,
   "type": "start|end|safety|check|decision|repair|process|io|document|subprocess|connector",
   "lane": str|null, "ref": str, "expected": str, "tools": str, "warning": str, "duration": str}],
 "edges": [{"source": str, "target": str, "label": str}]}
Structure attendue : start = symptome constate -> safety = mise en securite / consignation (EPI, coupure
energie, calage) -> suite de check (controles / mesures, une question fermee par noeud, `expected` = valeur
ou critere attendu avec unite) -> branches -> repair (action corrective : remplacer, regler, reparer)
-> check de verification du bon fonctionnement -> end (panne resolue / escalade expert).
Ordonne les controles du plus simple / probable au plus complexe / couteux.
Regles : ids courts [A-Za-z0-9_] uniques ; exactement un start ; au moins un end ; chaque check ou decision a
au moins deux sorties etiquetees (Oui/Non, OK/NOK, ou valeurs) ; `warning` obligatoire sur les safety et sur
toute etape a risque (haute tension, pression, chaleur, levage) ; `tools` = outillage necessaire ;
`ref` = reference document/tache si connue sinon "" ; `duration` estimee si pertinente sinon "" ;
un couloir par acteur cite (sinon lanes vide et lane null) ; system et fault_code = "" si inconnus ;
libelles concis a l'infinitif ; n'invente pas de valeurs constructeur :
si inconnue, expected = "selon constructeur" ;
langue du texte source."""

_LIST_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)]|[a-zA-Z][.)])\s*")
_DECISION = re.compile(r"(\?\s*$)|^(si|if|est-ce|verifier si|check if)\b", re.IGNORECASE)
_START = re.compile(r"^(debut|début|start|demarrage|démarrage|symptome|symptôme|panne)\b", re.IGNORECASE)
_END = re.compile(r"^(fin|end|stop|cloture|clôture|panne resolue|panne résolue)\b", re.IGNORECASE)
_IO = re.compile(r"^(saisir|lire|recevoir|imprimer|afficher|input|output|read|print)\b", re.IGNORECASE)
_DOC = re.compile(r"\b(rapport|document|formulaire|fiche|report|form)\b", re.IGNORECASE)
_SAFETY = re.compile(
    r"^(consigner|couper|debrancher|débrancher|isoler|caler|porter|mettre en securite|mettre en sécurité|"
    r"lockout|disconnect|isolate|wear)\b|\b(epi|ppe|consignation|haute tension|high voltage)\b",
    re.IGNORECASE,
)
_CHECK = re.compile(
    r"^(mesurer|controler|contrôler|verifier|vérifier|tester|inspecter|"
    r"lire les codes|measure|check|inspect|test)\b",
    re.IGNORECASE,
)
_REPAIR = re.compile(
    r"^(remplacer|reparer|réparer|regler|régler|resserrer|nettoyer|recharger|purger|replace|repair|adjust|tighten|"
    r"clean)\b",
    re.IGNORECASE,
)
_EXPECTED = re.compile(r"\s*\((?:attendu|expected|valeur)\s*[:=]\s*([^)]+)\)", re.IGNORECASE)


def _classify(line: str) -> str:
    for ntype, rx in (("start", _START), ("end", _END)):
        if rx.match(line):
            return ntype
    if _SAFETY.search(line):
        return "safety"
    if _CHECK.match(line):
        return "check"
    if _DECISION.search(line):
        return "decision"
    if _REPAIR.match(line):
        return "repair"
    if _IO.match(line):
        return "io"
    return "document" if _DOC.search(line) else "process"


_LIMITS = {"label": 500, "ref": 120, "expected": 300, "tools": 300, "warning": 500, "duration": 40}


def load_json_object(raw: str) -> object:
    """Premier objet JSON de la reponse LLM (tolere du texte autour)."""
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("aucun objet JSON dans la reponse")
    return json.loads(raw[start : end + 1])


def clip_graph_dict(data: object) -> object:
    """Tronque les champs texte trop longs avant validation Pydantic."""
    if isinstance(data, dict):
        for key, lim in (("title", 200), ("system", 200), ("fault_code", 60)):
            if isinstance(data.get(key), str):
                data[key] = data[key][:lim]
        for node in data.get("nodes") or []:
            if isinstance(node, dict):
                for key, lim in _LIMITS.items():
                    if isinstance(node.get(key), str):
                        node[key] = node[key][:lim]
    return data


def fallback_parse(text: str) -> tuple[FlowGraph, list[str]]:
    """Une ligne = une etape, liens sequentiels ; decisions detectees par heuristique."""
    lines = [_LIST_PREFIX.sub("", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln][:200]
    if not lines:
        raise AppError("TEXT_EMPTY", "Description vide", status_code=422)
    used: set[str] = set()
    nodes: list[dict[str, object]] = []
    if not _START.match(lines[0]):
        nodes.append({"id": slug_id("Debut", used), "label": "Debut", "type": "start"})
    for ln in lines:
        node: dict[str, object] = {"type": _classify(ln)}
        if m := _EXPECTED.search(ln):
            node["expected"] = m.group(1).strip()[:300]
            ln = _EXPECTED.sub("", ln).strip() or ln
        node.update(id=slug_id(ln, used), label=ln[:500])
        if node["type"] == "safety":
            node["warning"] = "Appliquer les consignes de securite du constructeur avant intervention."
        nodes.append(node)
    if nodes[-1]["type"] != "end":
        nodes.append({"id": slug_id("Fin", used), "label": "Fin", "type": "end"})
    end_id = next(n["id"] for n in reversed(nodes) if n["type"] == "end")

    edges: list[dict[str, object]] = []
    for cur, nxt in pairwise(nodes):
        if cur["type"] == "end":
            continue
        is_dec = cur["type"] == "decision" or (cur["type"] == "check" and str(cur["label"]).endswith("?"))
        edges.append({"source": cur["id"], "target": nxt["id"], "label": "Oui" if is_dec else ""})
        if is_dec and nxt["id"] != end_id:
            edges.append({"source": cur["id"], "target": end_id, "label": "Non"})
    warnings = ["Generation deterministe (sans IA) : verifier les branches des decisions."]
    return graph_from_dict({"title": "Logigramme", "nodes": nodes, "edges": edges}), warnings


async def parse_text(db: Session, text: str) -> tuple[FlowGraph, list[str], bool]:
    """Retourne (graphe, avertissements, llm_utilise)."""
    if not get_llm_enabled(db):
        graph, warnings = fallback_parse(text)
        return graph, ["LLM desactive.", *warnings], False
    try:
        client = MistralClient.from_db(db)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text[:20000]},
        ]
        chunks = [delta async for delta in client.chat_stream(messages, temperature=0.1)]
        graph = graph_from_dict(clip_graph_dict(load_json_object("".join(chunks))))
        return graph, [], True
    except (MistralError, AppError, ValueError) as exc:
        log.warning("llm_parse_fallback", reason=type(exc).__name__)
        reason = "LLM non configure." if isinstance(exc, MistralError) else "Reponse LLM inexploitable."
    except Exception as exc:  # erreurs reseau httpx et assimilees -> repli gracieux
        log.warning("llm_parse_fallback", reason=type(exc).__name__)
        reason = "LLM injoignable."
    graph, warnings = fallback_parse(text)
    return graph, [reason, *warnings], False
