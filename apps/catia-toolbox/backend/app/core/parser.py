"""Parsing d'arborescence — scan de dossier local OU listing CSV/JSON.

REGLE METIER : on ne lit JAMAIS le contenu des fichiers. Uniquement les
metadonnees (nom, taille, mtime, chemin relatif, extension). Aucune ecriture.

Sortie commune : `ParsedTree` = liste de `ParsedNode` (plats, avec un
`parent_path` permettant de reconstruire la hierarchie cote persistance).
Les chemins relatifs sont normalises en slash avant ("/") pour etre
deterministes et cross-plateforme.
"""

from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Optional

from app.core.errors import AppError


@dataclass
class ParsedNode:
    rel_path: str
    name: str
    ext: str
    kind: str  # "file" | "folder"
    depth: int
    size: int = 0
    mtime: Optional[datetime] = None
    parent_path: Optional[str] = None


@dataclass
class ParsedTree:
    root_label: str
    nodes: list[ParsedNode] = field(default_factory=list)

    @property
    def node_count(self) -> int:
        return len(self.nodes)


def _norm(rel: str) -> str:
    """Normalise un chemin relatif : slash avant, sans `./` ni `/` final."""
    rel = rel.replace("\\", "/").strip("/")
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    return "/".join(parts)


def _ext_of(name: str) -> str:
    suffix = PurePosixPath(name).suffix.lower()
    return suffix.lstrip(".")


def _parent_of(rel_path: str) -> Optional[str]:
    if "/" not in rel_path:
        return None
    return rel_path.rsplit("/", 1)[0]


# ----------------------------------------------------------------------------
# Mode 1 : scan d'un dossier local (metadonnees seules)
# ----------------------------------------------------------------------------


def scan_folder(root: str, max_nodes: int = 20000) -> ParsedTree:
    """Walk recursif d'un dossier. Lit nom/taille/mtime, jamais le contenu.

    - Ignore les liens symboliques (evite les boucles).
    - Plafonne a `max_nodes` (au-dela : AppError TREE_TOO_LARGE).
    """
    if not root or not root.strip():
        raise AppError("SCAN_PATH_EMPTY", "Chemin a scanner vide.", status_code=400)

    abs_root = os.path.abspath(os.path.expanduser(root.strip()))
    if not os.path.exists(abs_root):
        raise AppError(
            "SCAN_PATH_NOT_FOUND",
            "Le chemin a scanner n'existe pas.",
            status_code=404,
            detail={"path": abs_root},
        )
    if not os.path.isdir(abs_root):
        raise AppError(
            "SCAN_PATH_NOT_DIR",
            "Le chemin a scanner n'est pas un dossier.",
            status_code=400,
            detail={"path": abs_root},
        )

    nodes: list[ParsedNode] = []

    def _add(rel: str, kind: str, size: int, mtime: Optional[datetime]) -> None:
        if len(nodes) >= max_nodes:
            raise AppError(
                "TREE_TOO_LARGE",
                f"Arborescence trop volumineuse (> {max_nodes} noeuds). "
                "Affinez le dossier ou augmentez max_nodes.",
                status_code=413,
                detail={"max_nodes": max_nodes},
            )
        name = rel.rsplit("/", 1)[-1]
        nodes.append(
            ParsedNode(
                rel_path=rel,
                name=name,
                ext=_ext_of(name) if kind == "file" else "",
                kind=kind,
                depth=rel.count("/"),
                size=size,
                mtime=mtime,
                parent_path=_parent_of(rel),
            )
        )

    for dirpath, dirnames, filenames in os.walk(abs_root, topdown=True, followlinks=False):
        # On retire les sous-dossiers qui sont des liens symboliques (in place
        # pour que os.walk ne les explore pas).
        dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]

        rel_dir = _norm(os.path.relpath(dirpath, abs_root))
        # Le dossier racine lui-meme (rel_dir == "") n'est pas materialise.
        if rel_dir:
            _add(rel_dir, "folder", 0, _safe_mtime(dirpath))

        for fn in sorted(filenames):
            fpath = os.path.join(dirpath, fn)
            if os.path.islink(fpath):
                continue
            rel_file = _norm(os.path.join(rel_dir, fn)) if rel_dir else _norm(fn)
            _add(rel_file, "file", _safe_size(fpath), _safe_mtime(fpath))

    return ParsedTree(root_label=os.path.basename(abs_root) or abs_root, nodes=nodes)


def scan_paths(root: str, paths: list[str], max_nodes: int = 20000) -> ParsedTree:
    """Construit un ParsedTree depuis une selection mixte (fichiers ET dossiers).

    Les `rel_path` sont calcules relativement a `root` (racine OneDrive) afin de
    preserver la position des elements selectionnes dans l'arborescence. Un
    dossier selectionne est scanne recursivement ; un fichier est ajoute seul
    (avec ses dossiers parents synthetises). Metadonnees seules, jamais le
    contenu ; liens symboliques ignores.
    """
    abs_root = os.path.abspath(os.path.expanduser((root or "").strip()))
    by_path: dict[str, ParsedNode] = {}

    def _check_cap() -> None:
        if len(by_path) >= max_nodes:
            raise AppError(
                "TREE_TOO_LARGE",
                f"Selection trop volumineuse (> {max_nodes} noeuds).",
                status_code=413,
                detail={"max_nodes": max_nodes},
            )

    def _ensure_folder(rel: str) -> None:
        if not rel or rel in by_path:
            return
        parent = _parent_of(rel)
        if parent:
            _ensure_folder(parent)
        _check_cap()
        by_path[rel] = ParsedNode(
            rel_path=rel,
            name=rel.rsplit("/", 1)[-1],
            ext="",
            kind="folder",
            depth=rel.count("/"),
            parent_path=parent,
        )

    def _add_file(abs_path: str, rel: str) -> None:
        if not rel or rel in by_path:
            return
        parent = _parent_of(rel)
        if parent:
            _ensure_folder(parent)
        _check_cap()
        by_path[rel] = ParsedNode(
            rel_path=rel,
            name=rel.rsplit("/", 1)[-1],
            ext=_ext_of(rel),
            kind="file",
            depth=rel.count("/"),
            size=_safe_size(abs_path),
            mtime=_safe_mtime(abs_path),
            parent_path=parent,
        )

    for raw in paths:
        abs_p = os.path.abspath(os.path.expanduser(str(raw).strip()))
        if not os.path.exists(abs_p) or os.path.islink(abs_p):
            continue
        rel = _norm(os.path.relpath(abs_p, abs_root))
        # Hors racine (relpath remonte avec '..') : on ignore.
        if rel.startswith(".."):
            continue

        if os.path.isdir(abs_p):
            _ensure_folder(rel)
            for dirpath, dirnames, filenames in os.walk(abs_p, topdown=True, followlinks=False):
                dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
                rel_dir = _norm(os.path.relpath(dirpath, abs_root))
                if rel_dir:
                    _ensure_folder(rel_dir)
                for fn in sorted(filenames):
                    fpath = os.path.join(dirpath, fn)
                    if os.path.islink(fpath):
                        continue
                    rel_file = _norm(os.path.join(rel_dir, fn)) if rel_dir else _norm(fn)
                    _add_file(fpath, rel_file)
        elif os.path.isfile(abs_p):
            _add_file(abs_p, rel)

    nodes = sorted(by_path.values(), key=lambda n: (n.depth, n.kind != "folder", n.rel_path))
    root_label = os.path.basename(abs_root) or abs_root or "selection"
    return ParsedTree(root_label=root_label, nodes=nodes)


def list_files(root_path: str, max_nodes: int = 20000) -> list[dict]:
    """Liste a plat tous les FICHIERS sous `root_path` (recursif, metadonnees seules).

    Reutilise `scan_folder` (memes garde-fous : symlinks ignores, cap `max_nodes`)
    et reconstruit le chemin absolu de chaque fichier. Sert au selecteur de
    fichiers recursif (choisir des fichiers dans un dossier sans tout importer).
    """
    abs_root = os.path.abspath(os.path.expanduser((root_path or "").strip()))
    tree = scan_folder(root_path, max_nodes=max_nodes)
    out: list[dict] = []
    for n in tree.nodes:
        if n.kind != "file":
            continue
        abs_p = os.path.join(abs_root, *n.rel_path.split("/"))
        out.append(
            {
                "name": n.name,
                "path": abs_p,
                "rel": n.rel_path,
                "ext": n.ext,
                "size": n.size,
                "mtime": n.mtime,
            }
        )
    return out


def _safe_size(path: str) -> int:
    try:
        return int(os.path.getsize(path))
    except OSError:
        return 0


def _safe_mtime(path: str) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    except OSError:
        return None


# ----------------------------------------------------------------------------
# Mode 2 : import d'un listing CSV / JSON
# ----------------------------------------------------------------------------


def parse_listing(raw: bytes, ext: str, *, root_label: str = "listing", max_nodes: int = 20000) -> ParsedTree:
    """Parse un listing exporte (CSV ou JSON) en arborescence.

    CSV : colonnes `path` (requise), `size`, `date`/`mtime`/`modified` (option).
    JSON : liste d'objets `{path, size, date}` OU liste de chaines de chemins.
    Les dossiers intermediaires sont synthetises depuis les prefixes de chemins.
    """
    ext = ext.lstrip(".").lower()
    if ext == "csv":
        entries = _entries_from_csv(raw)
    elif ext == "json":
        entries = _entries_from_json(raw)
    else:
        raise AppError(
            "LISTING_EXT_UNSUPPORTED",
            "Format de listing non supporte (csv ou json attendu).",
            status_code=400,
            detail={"ext": ext},
        )

    if not entries:
        raise AppError("LISTING_EMPTY", "Listing vide ou sans colonne 'path'.", status_code=400)

    return _build_from_entries(entries, root_label=root_label, max_nodes=max_nodes)


def _entries_from_csv(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8-sig", errors="replace")
    # Detection simple du delimiteur (`,` ou `;`).
    sample = text[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    out: list[dict] = []
    for row in reader:
        norm = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        path = norm.get("path") or norm.get("chemin") or norm.get("relpath")
        if not path:
            continue
        out.append(
            {
                "path": path,
                "size": norm.get("size") or norm.get("taille") or "",
                "date": norm.get("date") or norm.get("mtime") or norm.get("modified") or "",
                "kind": norm.get("kind") or norm.get("type") or "",
            }
        )
    return out


def _entries_from_json(raw: bytes) -> list[dict]:
    try:
        data = json.loads(raw.decode("utf-8-sig", errors="replace"))
    except json.JSONDecodeError as e:
        raise AppError("LISTING_JSON_INVALID", f"JSON invalide : {e}", status_code=400) from e

    # Tolere {"files": [...]} ou {"nodes": [...]} ou directement une liste.
    if isinstance(data, dict):
        data = data.get("files") or data.get("nodes") or data.get("paths") or []

    out: list[dict] = []
    if not isinstance(data, list):
        raise AppError("LISTING_JSON_SHAPE", "JSON attendu : liste de chemins ou d'objets.", status_code=400)

    for item in data:
        if isinstance(item, str):
            out.append({"path": item, "size": "", "date": "", "kind": ""})
        elif isinstance(item, dict):
            path = item.get("path") or item.get("chemin") or item.get("relpath")
            if not path:
                continue
            out.append(
                {
                    "path": str(path),
                    "size": item.get("size") or item.get("taille") or "",
                    "date": item.get("date") or item.get("mtime") or item.get("modified") or "",
                    "kind": item.get("kind") or item.get("type") or "",
                }
            )
    return out


def _build_from_entries(entries: list[dict], *, root_label: str, max_nodes: int) -> ParsedTree:
    by_path: dict[str, ParsedNode] = {}

    def _ensure_folder(rel: str) -> None:
        if not rel or rel in by_path:
            return
        # Cree d'abord les ancetres.
        parent = _parent_of(rel)
        if parent:
            _ensure_folder(parent)
        by_path[rel] = ParsedNode(
            rel_path=rel,
            name=rel.rsplit("/", 1)[-1],
            ext="",
            kind="folder",
            depth=rel.count("/"),
            parent_path=parent,
        )

    for entry in entries:
        raw_path = str(entry.get("path", ""))
        is_folder = raw_path.rstrip().endswith("/") or str(entry.get("kind", "")).lower() in ("folder", "dir", "directory")
        rel = _norm(raw_path)
        if not rel:
            continue
        parent = _parent_of(rel)
        if parent:
            _ensure_folder(parent)

        if is_folder:
            _ensure_folder(rel)
            continue

        by_path[rel] = ParsedNode(
            rel_path=rel,
            name=rel.rsplit("/", 1)[-1],
            ext=_ext_of(rel),
            kind="file",
            depth=rel.count("/"),
            size=_to_int(entry.get("size")),
            mtime=_to_dt(entry.get("date")),
            parent_path=parent,
        )

    if len(by_path) > max_nodes:
        raise AppError(
            "TREE_TOO_LARGE",
            f"Listing trop volumineux (> {max_nodes} noeuds).",
            status_code=413,
            detail={"max_nodes": max_nodes},
        )

    # Tri stable : dossiers puis fichiers, par profondeur croissante.
    nodes = sorted(by_path.values(), key=lambda n: (n.depth, n.kind != "folder", n.rel_path))
    return ParsedTree(root_label=root_label, nodes=nodes)


def _to_int(v: object) -> int:
    try:
        return int(float(str(v).strip())) if str(v).strip() else 0
    except (ValueError, TypeError):
        return 0


def _to_dt(v: object) -> Optional[datetime]:
    s = str(v or "").strip()
    if not s:
        return None
    for parse in (_parse_iso, _parse_epoch):
        dt = parse(s)
        if dt is not None:
            return dt
    return None


def _parse_iso(s: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_epoch(s: str) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(float(s), tz=timezone.utc)
    except (ValueError, OSError):
        return None
