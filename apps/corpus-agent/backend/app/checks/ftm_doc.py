"""Vue structurée d'un livrable FTM + fabrique d'anomalies — socle des
checks v4.

Les parsers Excel produisent un `extracted_text` ligne à ligne : un marqueur
`[ONGLET: titre]` précède chaque feuille, puis chaque ligne non vide rend ses
cellules jointes par ` | `. Ce module reconstruit, sans relire le fichier,
une vue `{onglet -> lignes}` (chaque ligne = liste de cellules) exploitable
par tous les modules de `app/checks/`.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Optional

from app.db.models import Anomaly, FileVersion, File, Project

_ONGLET_RE = re.compile(r"\[ONGLET\s*:\s*([^\]]+)\]")
_CELL_SEP = " | "
# Numéro d'opération / tâche en début de ligne : « 2.3 |… », « 3.1.4 | … ».
_TASK_NUM_RE = re.compile(r"^\s*(\d+(?:\.\d+){0,3})\s*\|")
_MAX_LOC = 240  # cap d'affichage du champ location dans l'UI


def latest_version(f: File) -> Optional[FileVersion]:
    """Dernière version uploadée d'un fichier, ou None si aucune."""
    if not f.versions:
        return None
    return sorted(f.versions, key=lambda v: v.uploaded_at)[-1]


def parse_sheets(text: str) -> dict[str, list[list[str]]]:
    """`{titre_onglet -> [[cellules], ...]}`. Pour un document sans marqueur
    `[ONGLET: …]` (docx/pdf), renvoie `{'': lignes}`.

    Les cellules sont conservées **brutes** (espaces de tête/fin préservés)
    pour permettre au check `texte` de détecter un espace en début de phrase ;
    les autres checks strippent à la demande."""
    out: dict[str, list[list[str]]] = {"": []}
    current = ""
    for raw in (text or "").split("\n"):
        stripped = raw.strip()
        m = _ONGLET_RE.match(stripped)
        if m:
            current = m.group(1).strip()
            out.setdefault(current, [])
            continue
        if not stripped:
            continue
        out.setdefault(current, []).append(raw.rstrip("\r").split(_CELL_SEP))
    if len(out) > 1 and not out.get(""):
        out.pop("", None)
    return out


def find_sheet(
    sheets: dict[str, list[list[str]]], *keywords: str
) -> tuple[str, list[list[str]]]:
    """`(titre, lignes)` du premier onglet dont le titre contient un mot-clé
    (insensible à la casse). `('', [])` si aucun."""
    kws = [k.lower() for k in keywords]
    for title, rows in sheets.items():
        tl = title.lower()
        if any(k in tl for k in kws):
            return title, rows
    return "", []


def locate(text: str, pos: int, *, file_name: str = "", extra: str = "") -> str:
    """Reconstruit un repère lisible pour le rédacteur à partir d'une position
    dans `extracted_text`.

    Format : `[fichier]` (si fourni) + onglet + n° de tâche éventuel + extrait
    de la ligne contenant `pos`. Exemple :
        `monfichier.xlsm | Tâche de maintenance | 2.3 | Ouvrir les 2 portes…`

    Si la position est hors `text`, retourne `file_name` ou `extra`.
    """
    if not text or pos < 0 or pos > len(text):
        return " | ".join(p for p in (file_name, extra) if p)[:_MAX_LOC]
    line_start = text.rfind("\n", 0, pos) + 1
    line_end = text.find("\n", pos)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end].strip()
    # Onglet courant = dernier marqueur `[ONGLET: …]` avant la ligne.
    onglet = ""
    for m in _ONGLET_RE.finditer(text[:line_start]):
        onglet = m.group(1).strip()
    # Numéro de tâche éventuel — on le sépare de `line` pour éviter le doublon.
    task_num = ""
    m_task = _TASK_NUM_RE.match(line)
    if m_task:
        task_num = m_task.group(1)
        line = line[m_task.end():].lstrip()
    parts: list[str] = []
    if file_name:
        parts.append(file_name)
    if onglet:
        parts.append(onglet)
    if task_num:
        parts.append(task_num)
    if line:
        parts.append(line)
    if extra:
        parts.append(extra)
    return " | ".join(parts)[:_MAX_LOC]


def find_column(rows: list[list[str]], *header_keywords: str) -> int:
    """Index de la première colonne dont l'en-tête (cherché dans les 8
    premières lignes) contient un mot-clé. `-1` si introuvable."""
    kws = [k.lower() for k in header_keywords]
    for row in rows[:8]:
        for idx, cell in enumerate(row):
            cl = cell.lower()
            if any(k in cl for k in kws):
                return idx
    return -1


def make_anomaly(
    project: Project,
    file_version: Optional[FileVersion],
    run_id: uuid.UUID,
    atype: str,
    severity: str,
    message: str,
    suggestion: str = "",
    location: str = "",
    confidence: str = "elevee",
    message_key: Optional[str] = None,
    message_params: Optional[dict[str, Any]] = None,
    suggestion_key: Optional[str] = None,
    suggestion_params: Optional[dict[str, Any]] = None,
) -> Anomaly:
    """Fabrique une `Anomaly` `status="open"` — signature unique pour tous
    les checks v4. `confidence` ∈ {elevee, moyenne, faible} : par défaut
    `elevee` (contrôle déterministe) ; les checks IA passent leur propre
    niveau.

    Pour le rendu i18n côté front, un check peut renseigner `message_key`
    et `message_params` (idem pour la suggestion). Le front fait
    `t(message_key, params)` et retombe sur `message` (FR) si la clé est
    absente du bundle. Les checks legacy qui ne fournissent pas de clé
    restent FR-only — pas de régression."""
    params_msg = json.dumps(message_params, ensure_ascii=False) if message_params else None
    params_sug = json.dumps(suggestion_params, ensure_ascii=False) if suggestion_params else None
    return Anomaly(
        project_id=project.id,
        file_version_id=file_version.id if file_version is not None else None,
        run_id=run_id,
        type=atype,
        severity=severity,
        confidence=confidence if confidence in ("elevee", "moyenne", "faible") else "elevee",
        message=message,
        suggestion=suggestion,
        message_key=message_key,
        message_params_json=params_msg,
        suggestion_key=suggestion_key,
        suggestion_params_json=params_sug,
        location=location[:500],
        status="open",
    )
