"""Versioned fingerprints for persisted DM XML."""

import hashlib
import json
from pathlib import Path

from app.core.s1000d_serializer import SERIALIZER_VERSION
from app.db.models import Document


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def xml_context_fingerprint(doc: Document, brex_xml: str | None) -> str:
    paths = [doc.dmrl_path, doc.dm_header_path, doc.cir_path, doc.brex_rules_path]
    resources = []
    for name in paths:
        if not name:
            continue
        path = Path(name)
        if path.is_file():
            stat = path.stat()
            resources.append((name, stat.st_mtime_ns, stat.st_size))
        else:
            resources.append((name, "missing"))
    return _digest(
        {
            "version": SERIALIZER_VERSION,
            "issue": doc.s1000d_issue,
            "brex": brex_xml,
            "header": doc.dm_header_json,
            "dmrl": doc.dmrl_json,
            "review": doc.preliminary_review_json,
            "resources": resources,
        }
    )


def dm_xml_fingerprint(dm: dict, context: str) -> str:
    return _digest(
        {
            "context": context,
            "tree": dm.get("tree"),
            "type": dm.get("dm_type"),
            "title": dm.get("title"),
            "dmc": dm.get("dmc"),
            "xml": dm.get("xml"),
        }
    )
