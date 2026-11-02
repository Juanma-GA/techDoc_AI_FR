"""Shared reference context for multi-DM ZIP exports."""

from __future__ import annotations

import struct
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pymupdf as fitz
from sqlalchemy.orm import Session

from app.core import ir as ir_mod
from app.core import wizard_resources as wres
from app.core import wizard_split as ws
from app.core.errors import AppError
from app.core.s1000d_serializer import ReferenceIndex, build_reference_index
from app.db.models import Document

ImageFormat = Literal["original", "jpeg", "png"]


@dataclass(frozen=True)
class ZipImageExport:
    archive_path: str
    source_path: Path
    target_format: Literal["jpeg", "png"] | None = None
    max_dimension: int | None = None

    def write_to(self, archive: zipfile.ZipFile) -> None:
        if self.target_format is None:
            archive.write(self.source_path, self.archive_path)
            return
        try:
            with fitz.open(str(self.source_path)) as image:
                page = image[0]
                width, height = _image_dimensions(self.source_path)
                target_max = min(self.max_dimension or max(width, height), max(width, height))
                scale = target_max / max(page.rect.width, page.rect.height)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale),
                                        alpha=self.target_format == "png")
                archive.writestr(self.archive_path, pixmap.tobytes(self.target_format))
        except (OSError, RuntimeError, ValueError) as exc:
            raise AppError("IMAGE_EXPORT_FAILED", "Impossible de convertir l'image exportee.", 500) from exc


def _image_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as source:
        header = source.read(24)
        if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) == 24:
            width, height = struct.unpack(">II", header[16:24])
            if width and height:
                return width, height
        if not header.startswith(b"\xff\xd8"):
            raise ValueError("Invalid image header.")
        source.seek(2)
        while True:
            marker = source.read(1)
            if not marker:
                raise ValueError("Incomplete JPEG header.")
            if marker != b"\xff":
                continue
            while marker == b"\xff":
                marker = source.read(1)
            if not marker or marker in {b"\xd9", b"\xda"}:
                raise ValueError("JPEG has no dimension marker.")
            if marker in {b"\x01", b"\xd8", *(bytes([value]) for value in range(0xd0, 0xd8))}:
                continue
            length_bytes = source.read(2)
            if len(length_bytes) != 2:
                raise ValueError("Incomplete JPEG segment.")
            length = int.from_bytes(length_bytes, "big")
            if length < 2:
                raise ValueError("Invalid JPEG segment.")
            if marker[0] in {0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf}:
                dimensions = source.read(5)
                if len(dimensions) != 5:
                    raise ValueError("Incomplete JPEG dimensions.")
                height, width = struct.unpack(">HH", dimensions[1:])
                if width and height:
                    return width, height
                raise ValueError("Image dimensions must be positive.")
            source.seek(length - 2, 1)


def pictogram_image_names(doc: Document) -> set[str]:
    names: set[str] = set()
    for dm in ws.load_dms(doc):
        if not dm.get("tree"):
            continue
        root = ir_mod.from_dict(dm["tree"])
        for node in root.walk():
            if node.kind != "figure" or not node.is_pictogram:
                continue
            if node.icn:
                names.add(node.icn.casefold())
            names.update(name.casefold() for name in node.icns)
    return names


def prepare_zip_images(
    paths: Sequence[Path],
    *,
    pictogram_names: set[str],
    max_dimension: int | None,
    image_format: ImageFormat,
) -> tuple[list[ZipImageExport], dict[str, str]]:

    exports: list[ZipImageExport] = []
    image_name_map: dict[str, str] = {}
    archive_paths: set[str] = set()

    for path in paths:
        suffix = path.suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png"}:
            raise AppError(
                "IMAGE_FORMAT_UNSUPPORTED",
                f"Format d'image non pris en charge : {path.name}.",
                422,
            )
        source_format = "png" if suffix == ".png" else "jpeg"
        target_format = source_format if image_format == "original" else image_format
        target_suffix = (
            path.suffix
            if image_format == "original"
            else ".png" if target_format == "png" else ".jpg"
        )
        output_name = f"{path.stem}{target_suffix}"
        is_pictogram = (
            path.name.casefold() in pictogram_names
            or path.stem.casefold().startswith("picto_")
        )
        directory = "pictograms" if is_pictogram else "illustrations"
        archive_path = f"{directory}/{output_name}"
        if archive_path in archive_paths:
            raise AppError(
                "IMAGE_EXPORT_NAME_COLLISION",
                "Le format choisi cree des noms d'images en double dans le ZIP.",
                422,
            )
        archive_paths.add(archive_path)

        try:
            width, height = _image_dimensions(path)
            resize = max_dimension is not None and max(width, height) > max_dimension
        except (OSError, RuntimeError, ValueError) as exc:
            raise AppError(
                "IMAGE_EXPORT_FAILED",
                f"Impossible de traiter l'image {path.name}.",
                500,
            ) from exc

        if output_name != path.name:
            image_name_map[path.name] = output_name
        exports.append(ZipImageExport(
            archive_path=archive_path, source_path=path,
            target_format=target_format if resize or target_format != source_format else None,
            max_dimension=max_dimension,
        ))

    return exports, image_name_map


def reference_index_documents(
    dms: list[dict],
    dmrl_by_dmc: dict[str, dict],
    issue: str,
    root_transform: Callable[[dict, ir_mod.IRNode], ir_mod.IRNode] | None = None,
) -> list[tuple[str, ir_mod.IRNode, dict[str, object]]]:
    documents = []
    for dm in dms:
        if not dm.get("tree"):
            continue
        metadata = dict(dmrl_by_dmc.get(dm.get("dmc"), {}))
        metadata.update({
            "dmc": dm.get("dmc") or metadata.get("dmc") or "",
            "dm_type": dm["dm_type"],
            "issue": issue,
        })
        root = ir_mod.from_dict(dm["tree"])
        if root_transform is not None:
            root = root_transform(dm, root)
        documents.append((
            str(dm["dm_id"]),
            root,
            metadata,
        ))
    return documents


def generate_zip_dm_xmls(
    doc: Document,
    dm_ids: Sequence[str],
    *,
    db: Session,
    dm_xml_generator: Callable[..., str],
    image_name_map: dict[str, str] | None = None,
    root_transform: Callable[[dict, ir_mod.IRNode], ir_mod.IRNode] | None = None,
) -> dict[str, str]:
    dms = ws.load_dms(doc)
    dmrl_by_dmc = {
        entry.dmc: entry.to_dict()
        for entry in wres.dmrl_entries(doc)
        if entry.dmc
    }
    reference_index: ReferenceIndex = build_reference_index(
        reference_index_documents(dms, dmrl_by_dmc, doc.s1000d_issue, root_transform)
    )
    xml_by_dm = {
        dm_id: dm_xml_generator(
            doc,
            dm_id,
            db=db,
            reference_index=reference_index,
            image_name_map=image_name_map,
        )
        for dm_id in dm_ids
    }
    return xml_by_dm
