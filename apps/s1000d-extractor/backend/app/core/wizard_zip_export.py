"""Shared reference context for multi-DM ZIP exports."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
    content: bytes


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
    import pymupdf as fitz

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
            source_bytes = path.read_bytes()
            source_pixmap = fitz.Pixmap(str(path))
            source_max = max(source_pixmap.width, source_pixmap.height)
            resize = max_dimension is not None and source_max > max_dimension
            if not resize and target_format == source_format:
                content = source_bytes
            else:
                with fitz.open(stream=source_bytes, filetype=source_format) as image_doc:
                    if image_doc.page_count != 1:
                        raise ValueError("An image export must contain exactly one page.")
                    page = image_doc[0]
                    page_max = max(page.rect.width, page.rect.height)
                    if page_max <= 0:
                        raise ValueError("Image dimensions must be positive.")
                    target_max = min(max_dimension or source_max, source_max)
                    scale = target_max / page_max
                    pixmap = page.get_pixmap(
                        matrix=fitz.Matrix(scale, scale),
                        alpha=target_format == "png",
                    )
                    content = pixmap.tobytes(target_format)
        except (OSError, RuntimeError, ValueError) as exc:
            raise AppError(
                "IMAGE_EXPORT_FAILED",
                f"Impossible de traiter l'image {path.name}.",
                500,
            ) from exc

        if output_name != path.name:
            image_name_map[path.name] = output_name
        exports.append(ZipImageExport(archive_path=archive_path, content=content))

    return exports, image_name_map


def reference_index_documents(
    dms: list[dict],
    dmrl_by_dmc: dict[str, dict],
    issue: str,
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
        documents.append((
            str(dm["dm_id"]),
            ir_mod.from_dict(dm["tree"]),
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
) -> dict[str, str]:
    dms = ws.load_dms(doc)
    dmrl_by_dmc = {
        entry.dmc: entry.to_dict()
        for entry in wres.dmrl_entries(doc)
        if entry.dmc
    }
    reference_index: ReferenceIndex = build_reference_index(
        reference_index_documents(dms, dmrl_by_dmc, doc.s1000d_issue)
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
