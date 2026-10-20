"""Parseur tabulaire (xlsx / csv).

Colonnes reconnues (en-tete insensible a la casse et aux accents, FR ou EN) :
    ID | Libelle | Type | Acteur | Suivants | Conditions
    + details optionnels : Reference | Valeur attendue | Outillage | Securite | Duree
Classeur : la feuille `Etapes` est lue si elle existe (export de l'outil), sinon la premiere.
`Suivants` : identifiants separes par `;` ou `,`.
`Conditions` : etiquettes alignees sur `Suivants` (meme separateur).
"""

from __future__ import annotations

import csv
import io
import re

from app.core.errors import AppError
from app.flow.model import FlowGraph, slug_id
from app.flow.parsers.json_dsl import graph_from_dict

_ACCENTS = str.maketrans("éèêëàâäîïôöùûüç", "eeeeaaaiioouuuc")
_ALIASES = {
    "id": "id",
    "identifiant": "id",
    "code": "id",
    "etape": "id",
    "step": "id",
    "libelle": "label",
    "label": "label",
    "description": "label",
    "activite": "label",
    "activity": "label",
    "type": "type",
    "forme": "type",
    "shape": "type",
    "acteur": "lane",
    "actor": "lane",
    "role": "lane",
    "responsable": "lane",
    "lane": "lane",
    "couloir": "lane",
    "suivants": "next",
    "suivant": "next",
    "next": "next",
    "successeurs": "next",
    "vers": "next",
    "conditions": "cond",
    "condition": "cond",
    "labels": "cond",
    "etiquettes": "cond",
    "reference": "ref",
    "ref": "ref",
    "ref. doc": "ref",
    "procedure": "ref",
    "valeur attendue": "expected",
    "attendu": "expected",
    "expected": "expected",
    "critere": "expected",
    "outillage": "tools",
    "outils": "tools",
    "tools": "tools",
    "equipement": "tools",
    "securite": "warning",
    "warning": "warning",
    "avertissement": "warning",
    "precautions": "warning",
    "duree": "duration",
    "duration": "duration",
    "temps": "duration",
}
_DETAIL_MAX = {"ref": 120, "expected": 300, "tools": 300, "warning": 500, "duration": 40}
_SPLIT = re.compile(r"[;,|\n]")
MAX_ROWS = 500


def _norm(header: object) -> str | None:
    key = str(header or "").strip().lower().translate(_ACCENTS)
    return _ALIASES.get(key)


def _lane_id(lane: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", lane.translate(_ACCENTS)).strip("_")[:64] or "lane"


def _rows_from_xlsx(content: bytes) -> list[list[object]]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl leve des exceptions heterogenes
        raise AppError("TABLE_UNREADABLE", "Classeur Excel illisible", status_code=422) from exc
    ws = wb["Etapes"] if "Etapes" in wb.sheetnames else wb.worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True, max_row=MAX_ROWS + 1)]
    wb.close()
    return rows


def _rows_from_csv(content: bytes) -> list[list[object]]:
    text = content.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
    return [list(r) for r in csv.reader(io.StringIO(text), dialect)][: MAX_ROWS + 1]


def parse_table(content: bytes, filename: str) -> tuple[FlowGraph, list[str]]:
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        rows = _rows_from_xlsx(content)
    elif name.endswith((".csv", ".txt")):
        rows = _rows_from_csv(content)
    else:
        raise AppError("TABLE_FORMAT", "Format attendu : .xlsx, .xlsm ou .csv", status_code=415)
    rows = [r for r in rows if any(str(c or "").strip() for c in r)]
    if len(rows) < 2:
        raise AppError(
            "TABLE_EMPTY", "Le tableau doit contenir un en-tete et au moins une ligne", status_code=422
        )

    cols: dict[str, int] = {}
    for idx, header in enumerate(rows[0]):
        key = _norm(header)
        if key and key not in cols:
            cols[key] = idx
    if "label" not in cols:
        raise AppError(
            "TABLE_COLUMNS",
            "Colonne Libelle introuvable",
            status_code=422,
            detail={"headers": [str(h or "") for h in rows[0]]},
        )

    def cell(row: list[object], key: str) -> str:
        idx = cols.get(key)
        return str(row[idx]).strip() if idx is not None and idx < len(row) and row[idx] is not None else ""

    warnings: list[str] = []
    used: set[str] = set()
    nodes: list[dict[str, object]] = []
    lanes: dict[str, str] = {}
    raw_ids: dict[str, str] = {}
    pending: list[tuple[str, str, str]] = []
    for lineno, row in enumerate(rows[1:], start=2):
        label = cell(row, "label")
        if not label:
            warnings.append(f"Ligne {lineno} sans libelle ignoree")
            continue
        raw_id = cell(row, "id") or label
        nid = slug_id(raw_id, used)
        raw_ids.setdefault(raw_id, nid)
        lane = cell(row, "lane")
        lane_id = _lane_id(lane) if lane else None
        if lane_id:
            lanes.setdefault(lane_id, lane)
        node: dict[str, object] = {
            "id": nid,
            "label": label[:500],
            "type": cell(row, "type") or "process",
            "lane": lane_id,
        }
        for key, limit in _DETAIL_MAX.items():
            value = cell(row, key)
            if value:
                node[key] = value[:limit]
        nodes.append(node)
        pending.append((nid, cell(row, "next"), cell(row, "cond")))

    edges: list[dict[str, str]] = []
    implicit = "next" not in cols
    for i, (nid, nxt, cond) in enumerate(pending):
        targets = [t.strip() for t in _SPLIT.split(nxt) if t.strip()]
        labels = [c.strip() for c in _SPLIT.split(cond)] if cond else []
        if implicit and i + 1 < len(pending):
            targets = [pending[i + 1][0]]
        for j, target in enumerate(targets):
            tid = raw_ids.get(target) or (target if target in used else None)
            if tid is None:
                warnings.append(f"Suivant inconnu '{target}' depuis {nid}")
                continue
            edges.append({"source": nid, "target": tid, "label": labels[j] if j < len(labels) else ""})

    graph = graph_from_dict(
        {
            "title": filename.rsplit(".", 1)[0][:200] or "Logigramme",
            "lanes": [{"id": k, "label": v} for k, v in lanes.items()],
            "nodes": nodes,
            "edges": edges,
        }
    )
    return graph, warnings
