"""Remove non-part Composer nodes from CLitServerModifiable sections."""

from __future__ import annotations

import io
import os
import re
import shutil
import stat
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Literal, TypedDict

_ALLOWED_CHILDREN = {"CLitAssyRoot", "Neutral", "Tracks", "CLitActorMesh"}
_XML_ENCODING = re.compile(rb"\bencoding\s*=\s*(['\"])([^'\"]+)\1", re.IGNORECASE)

FileStatus = Literal["ready", "optimized", "unchanged", "no_section", "invalid_xml", "error"]


class FileResult(TypedDict):
    path: str
    status: FileStatus
    removed_elements: int
    removed_by_tag: dict[str, int]
    backup_path: str | None
    message: str


class FolderResult(TypedDict):
    path: str
    applied: bool
    files_scanned: int
    files_with_changes: int
    files_modified: int
    removed_elements: int
    files: list[FileResult]


class FolderProgressEvent(TypedDict):
    type: Literal["progress"]
    files_scanned: int
    files_total: int


class FolderCompleteEvent(TypedDict):
    type: Literal["complete"]
    result: FolderResult


def _local_name(tag: object) -> str | None:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else None


def _remove_child(parent: ET.Element, child: ET.Element) -> None:
    siblings = list(parent)
    index = siblings.index(child)
    if child.tail:
        if index:
            previous = siblings[index - 1]
            previous.tail = (previous.tail or "") + child.tail
        else:
            parent.text = (parent.text or "") + child.tail
    parent.remove(child)


def _extract_actor_meshes(group: ET.Element, removed: Counter[str]) -> list[ET.Element]:
    meshes: list[ET.Element] = []
    for child in list(group):
        tag = _local_name(child.tag)
        if tag == "CLitActorMesh":
            meshes.append(child)
            continue
        if tag is not None:
            removed[tag] += 1
        meshes.extend(_extract_actor_meshes(child, removed))
    return meshes


def _filter_children(parent: ET.Element, removed: Counter[str]) -> bool:
    contains_mesh = False
    for child in list(parent):
        tag = _local_name(child.tag)
        if tag is None:
            continue
        if tag == "CLitAssyGroup":
            meshes = _extract_actor_meshes(child, removed)
            removed[tag] += 1
            if meshes:
                insertion_index = list(parent).index(child)
                group_tail = child.tail
                child.tail = None
                parent.remove(child)
                for offset, mesh in enumerate(meshes):
                    parent.insert(insertion_index + offset, mesh)
                meshes[-1].tail = group_tail
                contains_mesh = True
            else:
                _remove_child(parent, child)
        elif tag not in _ALLOWED_CHILDREN:
            _remove_child(parent, child)
            removed[tag] += 1
        elif tag == "CLitActorMesh":
            contains_mesh = True
        elif tag == "CLitAssyRoot":
            contains_mesh = _filter_children(child, removed) or contains_mesh
    return contains_mesh


def _serialize(tree: ET.ElementTree, source: bytes) -> bytes:
    declaration = source.lstrip(b"\xef\xbb\xbf \t\r\n").startswith(b"<?xml")
    encoding_match = _XML_ENCODING.search(source[:256]) if declaration else None
    encoding = encoding_match.group(2).decode("ascii") if encoding_match else "utf-8"
    output = io.BytesIO()
    tree.write(output, encoding=encoding, xml_declaration=declaration)
    return output.getvalue()


def _next_backup_path(path: Path) -> Path:
    backup_directory = path.parent / "sauvegarde"
    backup_directory.mkdir(exist_ok=True)
    candidate = backup_directory / f"{path.name}.bak"
    counter = 1
    while candidate.exists():
        candidate = backup_directory / f"{path.name}.bak.{counter}"
        counter += 1
    return candidate


def _atomic_write(path: Path, content: bytes) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _process_file(path: Path, *, apply: bool) -> FileResult:
    try:
        source = path.read_bytes()
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
        tree = ET.parse(io.BytesIO(source), parser=parser)
    except ET.ParseError as exc:
        return {
            "path": str(path),
            "status": "invalid_xml",
            "removed_elements": 0,
            "removed_by_tag": {},
            "backup_path": None,
            "message": str(exc),
        }
    except OSError as exc:
        return {
            "path": str(path),
            "status": "error",
            "removed_elements": 0,
            "removed_by_tag": {},
            "backup_path": None,
            "message": str(exc),
        }

    sections = [
        node
        for node in tree.getroot().iter()
        if _local_name(node.tag) == "Server" and node.get("Type") == "CLitServerModifiable"
    ]
    if not sections:
        return {
            "path": str(path),
            "status": "no_section",
            "removed_elements": 0,
            "removed_by_tag": {},
            "backup_path": None,
            "message": "",
        }

    removed: Counter[str] = Counter()
    for section in sections:
        _filter_children(section, removed)

    removed_elements = sum(removed.values())
    if not removed_elements:
        return {
            "path": str(path),
            "status": "unchanged",
            "removed_elements": 0,
            "removed_by_tag": {},
            "backup_path": None,
            "message": "",
        }

    if not apply:
        return {
            "path": str(path),
            "status": "ready",
            "removed_elements": removed_elements,
            "removed_by_tag": dict(removed),
            "backup_path": None,
            "message": "",
        }

    backup_path: Path | None = None
    try:
        output = _serialize(tree, source)
        backup_path = _next_backup_path(path)
        shutil.copy2(path, backup_path)
        _atomic_write(path, output)
    except (OSError, LookupError, UnicodeError) as exc:
        return {
            "path": str(path),
            "status": "error",
            "removed_elements": removed_elements,
            "removed_by_tag": dict(removed),
            "backup_path": str(backup_path) if backup_path and backup_path.exists() else None,
            "message": str(exc),
        }

    return {
        "path": str(path),
        "status": "optimized",
        "removed_elements": removed_elements,
        "removed_by_tag": dict(removed),
        "backup_path": str(backup_path),
        "message": "",
    }


def _list_smgxml_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise NotADirectoryError(str(directory))

    files: list[Path] = []
    with os.scandir(directory) as entries:
        for entry in entries:
            try:
                if (
                    not entry.is_symlink()
                    and entry.is_file(follow_symlinks=False)
                    and entry.name.casefold().endswith(".smgxml")
                ):
                    files.append(Path(entry.path))
            except OSError:
                continue

    return sorted(files, key=lambda item: item.name.casefold())


def count_smgxml_files(folder: str | Path) -> int:
    """Count top-level SMGXML filenames without opening their contents."""
    return len(_list_smgxml_files(Path(folder)))


def iter_optimize_folder_events(
    folder: str | Path, *, apply: bool = False
) -> Iterator[FolderProgressEvent | FolderCompleteEvent]:
    directory = Path(folder)
    files = _list_smgxml_files(directory)
    results: list[FileResult] = []
    files_total = len(files)
    yield {"type": "progress", "files_scanned": 0, "files_total": files_total}

    for files_scanned, path in enumerate(files, start=1):
        results.append(_process_file(path, apply=apply))
        yield {
            "type": "progress",
            "files_scanned": files_scanned,
            "files_total": files_total,
        }

    yield {
        "type": "complete",
        "result": {
            "path": str(directory),
            "applied": apply,
            "files_scanned": len(results),
            "files_with_changes": sum(item["removed_elements"] > 0 for item in results),
            "files_modified": sum(item["status"] == "optimized" for item in results),
            "removed_elements": sum(item["removed_elements"] for item in results),
            "files": results,
        },
    }


def optimize_folder(folder: str | Path, *, apply: bool = False) -> FolderResult:
    for event in iter_optimize_folder_events(folder, apply=apply):
        if event["type"] == "complete":
            return event["result"]
    raise RuntimeError("Folder optimization ended without a result.")
