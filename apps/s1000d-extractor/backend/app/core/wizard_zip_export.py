"""Shared reference context for multi-DM ZIP exports."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from sqlalchemy.orm import Session

from app.core import ir as ir_mod
from app.core import wizard_resources as wres
from app.core import wizard_split as ws
from app.core.s1000d_serializer import ReferenceIndex, build_reference_index
from app.db.models import Document


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
    return {
        dm_id: dm_xml_generator(
            doc,
            dm_id,
            db=db,
            reference_index=reference_index,
        )
        for dm_id in dm_ids
    }
