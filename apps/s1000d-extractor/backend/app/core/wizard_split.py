"""Operations de l'etape "decoupage" du wizard + aperçu + historique undo.

Extrait de `wizard.py` (qui depassait 200 lignes) : ce module regroupe tout ce
qui manipule la liste des DMs a l'etape split — edition manuelle
(rename/exclude/merge/split), masquage du bruit (entetes/pieds), pile d'undo, et
generation d'un apercu debut/fin par DM. `wizard.py` garde la machine d'etapes.

N'importe PAS `wizard` (pas de cycle) : il ne connait que l'IR + le splitter.
"""

from __future__ import annotations

import json

from app.core import context_classifier
from app.core import dmrl
from app.core import ir as ir_mod
from app.core.dmrl import DmrlEntry, entry_from_dict
from app.db.models import Document

_HISTORY_MAX = 20   # profondeur max de la pile d'annulation


# --- etat DMs ----------------------------------------------------------------

def load_dms(doc: Document) -> list[dict]:
    return json.loads(doc.dms_json) if doc.dms_json else []


def save_dms(doc: Document, dms: list[dict]) -> None:
    doc.dms_json = json.dumps(dms, ensure_ascii=False)


def node_count(tree: dict) -> int:
    return 1 + sum(node_count(c) for c in tree.get("children", []))


# --- historique (undo) -------------------------------------------------------

def load_history(doc: Document) -> list[str]:
    return json.loads(doc.dms_history_json) if doc.dms_history_json else []


def push_history(doc: Document) -> None:
    """Empile un instantane (chaine JSON) de l'etat courant avant mutation."""
    hist = load_history(doc)
    hist.append(doc.dms_json or "[]")
    doc.dms_history_json = json.dumps(hist[-_HISTORY_MAX:], ensure_ascii=False)


def undo(doc: Document) -> None:
    """Restaure le dernier instantane (sans re-empiler)."""
    hist = load_history(doc)
    if not hist:
        return
    doc.dms_json = hist.pop()
    doc.dms_history_json = json.dumps(hist, ensure_ascii=False)


def reset_history(doc: Document) -> None:
    doc.dms_history_json = None


def can_undo(doc: Document) -> bool:
    return bool(load_history(doc))


# --- apercu debut/fin --------------------------------------------------------

_PREVIEW_KINDS = {"paragraph", "item", "section", "admonition", "figure"}


def _collect_snippets(tree: dict, width: int) -> list[dict]:
    out: list[dict] = []

    def walk(node: dict) -> None:
        txt = (node.get("text") or "").strip()
        if txt and node.get("kind") in _PREVIEW_KINDS:
            clipped = txt[:width].rstrip()
            if len(txt) > width:
                clipped += "…"
            out.append({
                "text": clipped,
                "page": node.get("page"),
                "kind": node.get("kind"),
                "zone": node.get("zone", "body"),
            })
        for child in node.get("children", []):
            walk(child)

    walk(tree)
    return out


def dm_preview(tree: dict, *, head: int = 3, tail: int = 3, width: int = 90) -> dict:
    """Extraits de debut/fin d'un DM (ordre de lecture) pour verifier ses
    frontieres. Renvoie {head, tail, total}. `tail` vide si le DM est court."""
    snippets = _collect_snippets(tree, width)
    total = len(snippets)
    head_s = snippets[:head]
    tail_s = snippets[-tail:] if total > head + tail else []
    return {"head": head_s, "tail": tail_s, "total": total}


# --- masquage du bruit (entetes / pieds) -------------------------------------

def _filter_zones_dict(tree: dict, zones: set[str]) -> dict:
    """Copie de l'arbre sans les noeuds dont la zone est dans `zones`."""
    kids = [
        _filter_zones_dict(c, zones)
        for c in tree.get("children", [])
        if c.get("zone", "body") not in zones
    ]
    return {**tree, "children": kids}


def hide_zones(doc: Document, zones: list[str]) -> None:
    zset = set(zones)
    dms = load_dms(doc)
    for dm in dms:
        dm["tree"] = _filter_zones_dict(dm["tree"], zset)
    save_dms(doc, dms)


# --- edition manuelle du decoupage -------------------------------------------

def _renumber(dms: list[dict]) -> list[dict]:
    for i, d in enumerate(dms, start=1):
        d["dm_id"] = f"dm{i}"
    return dms


def _retype(dm: dict) -> str:
    root = ir_mod.from_dict(dm["tree"])
    return context_classifier.guess_dm_type(dm["title"], root)


def _dmc_for_title(title: str, entries: list[DmrlEntry], used: set[str]) -> str:
    """Associe un titre edite au DMC DMRL encore disponible."""
    needle = dmrl.normalize(title)
    if not needle:
        return ""
    matches: list[tuple[int, str]] = []
    for entry in entries:
        candidate = dmrl.normalize(entry.title)
        if candidate == needle:
            rank = 3
        elif candidate.startswith(needle):
            rank = 2
        elif needle in candidate:
            rank = 1
        else:
            continue
        if entry.dmc and entry.dmc not in used:
            matches.append((rank, entry.dmc))
    if not matches:
        return ""
    best_rank = max(rank for rank, _dmc in matches)
    best = {dmc for rank, dmc in matches if rank == best_rank}
    return next(iter(best)) if len(best) == 1 else ""


def sync_dmcs(dms: list[dict], doc: Document) -> None:
    """Complete les DMC manquants sans jamais conserver un doublon."""
    entries = [entry_from_dict(item) for item in (json.loads(doc.dmrl_json) if doc.dmrl_json else [])]
    used: set[str] = set()
    for dm in dms:
        dmc = str(dm.get("dmc") or "")
        if dmc and dmc not in used:
            used.add(dmc)
        else:
            dm["dmc"] = _dmc_for_title(dm.get("title", ""), entries, used)
            if dm["dmc"]:
                used.add(dm["dmc"])


def split_one(dm: dict) -> list[dict]:
    """Scinde un DM en sous-DMs (1 par section enfant). Renvoie [dm] si on ne
    peut pas le scinder (aucune section enfant)."""
    root = ir_mod.from_dict(dm["tree"])
    units: list[list] = []
    lead: list = []
    for child in root.children:
        if child.kind == "section":
            syn = ir_mod.IRNode(id="x", kind="section", level=0, children=list(child.children))
            units.append([child.text or "Section", syn])
        elif units:
            units[-1][1].children.append(child)
        else:
            lead.append(child)
    parts: list[tuple] = []
    if lead:
        lead_root = ir_mod.IRNode(id="x", kind="section", level=0, children=lead)
        parts.append((dm["title"], lead_root))
    parts.extend((t, s) for t, s in units)
    if len(parts) < 2:
        return [dm]
    return [
        {"dm_id": "tmp", "title": t, "dm_type": context_classifier.guess_dm_type(t, s),
         "tree": ir_mod.to_dict(s), "xml": None, "violations": None}
        for t, s in parts
    ]


def apply_split_op(doc: Document, params: dict) -> None:
    op = params["op"]
    dms = load_dms(doc)
    if op == "rename":
        title = (params.get("title") or "").strip()
        for d in dms:
            if d["dm_id"] == params.get("id") and title:
                d["title"] = title
                d["dmc"] = ""
    elif op == "exclude":
        dms = _renumber([d for d in dms if d["dm_id"] != params.get("id")])
    elif op == "merge":
        ids = params.get("ids") or []
        sel = [d for d in dms if d["dm_id"] in ids]
        if len(sel) >= 2:
            first = sel[0]
            children: list = []
            for d in sel:
                children.extend(d["tree"].get("children", []))
            first["tree"]["children"] = children
            first["dm_type"] = _retype(first)
            first["dmc"] = ""
            dms = _renumber([d for d in dms if d["dm_id"] == first["dm_id"] or d["dm_id"] not in ids])
    elif op == "split":
        target = next((d for d in dms if d["dm_id"] == params.get("id")), None)
        if target:
            subs = split_one(target)
            if len(subs) >= 2:
                pos = dms.index(target)
                dms = _renumber(dms[:pos] + subs + dms[pos + 1:])
    sync_dmcs(dms, doc)
    save_dms(doc, dms)
