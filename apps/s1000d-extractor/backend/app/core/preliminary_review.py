"""Persisted human review. No decision is inferred from a missing detection."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import inspect, update
from sqlalchemy.orm import Session, object_session

from app.core import preliminary_detection as detection
from app.core.errors import AppError
from app.core.preliminary_rules import RulesConfig, defaults, read_rules
from app.core.wizard_split import load_dms
from app.db.models import Document

Destination = Literal[
    "conditions", "personnel", "support", "supplies", "spares", "safety",
    "common", "closing", "body", "discard",
]


class ReviewAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    revision: int = Field(ge=0)
    dm_id: str = Field(min_length=1)
    op: Literal["decide", "split", "complete", "restart", "cursor", "skip"]
    passage_id: str | None = None
    destination: Destination | None = None
    text: str | None = Field(default=None, min_length=1, max_length=100000)
    split_at: int | None = Field(default=None, gt=0)
    confirm_empty: bool = False
    page: int | None = Field(default=None, gt=0)
    scroll_top: float = Field(default=0, ge=0, allow_inf_nan=False)
    selected_id: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def load(doc: Document) -> dict:
    return json.loads(doc.preliminary_review_json) if doc.preliminary_review_json else {
        "revision": 0, "generation": 0, "active_dm_id": None, "reviews": {},
    }


def rules_for(doc: Document) -> RulesConfig:
    db = object_session(doc)
    if db is not None:
        return read_rules(db)
    if inspect(doc).transient:
        return defaults()
    raise AppError("RULES_SESSION_REQUIRED", "Session de base requise pour verifier les regles de revue.", 500)


def _fingerprint(doc: Document, dm: dict, generation: int, rules: RulesConfig) -> str:
    def source(node: dict) -> dict:
        return {
            key: ([source(child) for child in value] if key == "children" else value)
            for key, value in node.items()
            if key not in {"candidates", "confidence", "context", "reviewed_requirements"}
        }

    path = Path(doc.storage_path)
    stat = path.stat() if path.is_file() else None
    data = [detection.RULE_VERSION, rules.fingerprint, generation, doc.s1000d_issue,
            [stat.st_size, stat.st_mtime_ns] if stat else None,
            doc.pdf_cut_start_page, doc.pdf_cut_end_page, source(dm["tree"])]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def _new_review(doc: Document, dm: dict, generation: int, rules: RulesConfig) -> dict:
    items = detection.passages(
        dm["tree"], source_format=doc.source_format,
        page_offset=load(doc).get(
            "page_offset", (doc.pdf_cut_start_page or 1) - 1 if doc.pdf_cut_path else 0,
        ),
        rules=rules,
    )
    return {
        "fingerprint": _fingerprint(doc, dm, generation, rules),
        "rules_revision": rules.revision,
        "status": "pending", "passages": items,
        "position": {"page": next((item["page"] for item in items if item["page"]), 1),
                     "scroll_top": 0, "selected_id": None},
        "saved_at": None,
    }


def prepare(doc: Document) -> None:
    state = load(doc)
    rules = rules_for(doc)
    changed = False
    for dm in load_dms(doc):
        if dm["dm_type"] != "procedural":
            continue
        if dm["dm_id"] not in state["reviews"]:
            state["reviews"][dm["dm_id"]] = _new_review(doc, dm, state["generation"], rules)
            changed = True
    if changed:
        state["revision"] += 1
        doc.preliminary_review_json = json.dumps(state, ensure_ascii=False)


def invalidate_source(doc: Document) -> None:
    state = load(doc)
    state["generation"] += 1
    state["revision"] += 1
    doc.preliminary_review_json = json.dumps(state, ensure_ascii=False)


def view(doc: Document) -> dict:
    state = load(doc)
    rules = rules_for(doc)
    reviews = {}
    for dm in load_dms(doc):
        if dm["dm_type"] != "procedural":
            continue
        review = state["reviews"].get(dm["dm_id"])
        if review is None:
            review = _new_review(doc, dm, state["generation"], rules)
        elif review["fingerprint"] != _fingerprint(doc, dm, state["generation"], rules):
            review = {**review, "status": "stale"}
        reviews[dm["dm_id"]] = review
    active = state["active_dm_id"]
    return {
        "revision": state["revision"],
        "active_dm_id": active if active in reviews else next(iter(reviews), None),
        "source_format": doc.source_format,
        "source_changed": any(item["status"] == "stale" for item in reviews.values())
        or bool(set(state["reviews"]) - set(reviews)),
        "reviews": reviews,
    }


def require_complete(doc: Document, dm_id: str | None = None) -> None:
    if not any(dm["dm_type"] == "procedural" for dm in load_dms(doc)):
        return
    reviews = view(doc)["reviews"]
    for key, review in reviews.items():
        if dm_id is not None and key != dm_id:
            continue
        if review["status"] == "skipped":
            continue
        if review["status"] != "reviewed" or any(
            item["decision"] not in detection.DESTINATIONS
            for item in review["passages"] if detection.is_reviewable(item)
        ):
            raise AppError(
                "PRELIMINARY_REVIEW_REQUIRED",
                "Terminez la revue des exigences preliminaires avant la generation ou l'export.",
                409, detail={"dm_id": key, "status": review["status"]},
            )


def apply(db: Session, doc: Document, action: ReviewAction) -> dict:
    if doc.wizard_step != "preliminary":
        raise AppError("REVIEW_STEP_REQUIRED", "Ouvrez l'etape de revue procedurale.", 409)
    previous = doc.preliminary_review_json
    state = load(doc)
    rules = read_rules(db)
    if action.revision != state["revision"]:
        raise AppError("REVIEW_CONFLICT", "La revue a change. Rechargez avant de modifier.", 409)
    dm = next((dm for dm in load_dms(doc) if dm["dm_id"] == action.dm_id), None)
    if dm is None or dm["dm_type"] != "procedural":
        raise AppError("REVIEW_DM_NOT_FOUND", "Procedure inconnue.", 404)
    if action.op == "skip":
        for candidate in load_dms(doc):
            if candidate["dm_type"] != "procedural":
                continue
            skipped = _new_review(doc, candidate, state["generation"], rules)
            skipped["status"] = "skipped"
            skipped["saved_at"] = _now()
            state["reviews"][candidate["dm_id"]] = skipped
    else:
        review = state["reviews"].get(action.dm_id)
        if action.op == "restart":
            review = _new_review(doc, dm, state["generation"], rules)
            state["reviews"][action.dm_id] = review
        elif review is None or review["fingerprint"] != _fingerprint(doc, dm, state["generation"], rules):
            raise AppError("REVIEW_STALE", "La source ou les regles ont change. Recommencez explicitement la revue.", 409)
        if action.op in {"decide", "split"}:
            item = next((p for p in review["passages"] if p["id"] == action.passage_id), None)
            if item is None:
                raise AppError("REVIEW_PASSAGE_NOT_FOUND", "Passage inconnu.", 404)
            if not detection.is_reviewable(item):
                raise AppError(
                    "REVIEW_STRUCTURE_ONLY",
                    "Ce titre, repere ou en-tete appartient a la structure source, pas aux exigences.",
                    422,
                )
            if action.op == "decide":
                if action.text is not None and not action.text.strip():
                    raise AppError("REVIEW_TEXT_INVALID", "Le passage ne peut pas etre vide.", 422)
                if "destination" in action.model_fields_set:
                    item["decision"] = action.destination
                if action.text is not None:
                    item["text"] = action.text
            else:
                at = action.split_at
                if at is None or at >= len(item["source_text"]) or not all(
                    part.strip() for part in (item["source_text"][:at], item["source_text"][at:])
                ):
                    raise AppError("REVIEW_SPLIT_INVALID", "Choisissez une coupure interne au passage source.", 422)
                if item["text"] != item["source_text"]:
                    raise AppError("REVIEW_SPLIT_EDITED", "Scindez le passage avant de corriger son texte.", 409)
                parts = []
                for start, end in ((0, at), (at, len(item["source_text"]))):
                    text = item["source_text"][start:end]
                    suggested, rule = detection.suggestion(
                        text, item.get("category_hint"), item.get("phase", "unknown"), item.get("admonition"),
                        rules=rules,
                    )
                    parts.append({
                        **item, "id": str(uuid4()), "start": item["start"] + start,
                        "end": item["start"] + end, "source_text": text, "text": text,
                        "decision": None, "suggested": suggested, "rule": rule,
                    })
                index = review["passages"].index(item)
                review["passages"][index:index + 1] = parts
                review["position"]["selected_id"] = None
            review["status"] = "pending"
        elif action.op == "complete":
            if not action.confirm_empty or any(
                item["decision"] not in detection.DESTINATIONS
                for item in review["passages"] if detection.is_reviewable(item)
            ):
                raise AppError(
                    "REVIEW_UNDECIDED", "Decidez de chaque passage et confirmez la verification du DM entier.",
                    409,
                )
            review["status"] = "reviewed"
        elif action.op == "cursor":
            pages = {p["page"] for p in review["passages"] if p["page"]} or {1}
            if action.page is not None and not min(pages) <= action.page <= max(pages):
                raise AppError("REVIEW_PAGE_INVALID", "Page hors de la procedure.", 422)
            if action.selected_id is not None and not any(
                p["id"] == action.selected_id for p in review["passages"]
            ):
                raise AppError("REVIEW_PASSAGE_NOT_FOUND", "Passage inconnu.", 404)
            review["position"] = {
                "page": action.page or review["position"]["page"],
                "scroll_top": action.scroll_top, "selected_id": action.selected_id,
            }
        review["saved_at"] = _now()
    state["active_dm_id"] = action.dm_id
    state["revision"] += 1
    encoded = json.dumps(state, ensure_ascii=False)
    # Compare-and-swap also protects against another tab writing after our read.
    result = db.execute(
        update(Document).where(
            Document.id == doc.id, Document.preliminary_review_json == previous,
            Document.dms_json == doc.dms_json, Document.wizard_step == "preliminary",
            rules.unchanged_condition(),
        ).values(preliminary_review_json=encoded),
        execution_options={"synchronize_session": False},
    )
    if result.rowcount != 1:
        db.rollback()
        raise AppError("REVIEW_CONFLICT", "Une autre sauvegarde a modifie la revue. Rechargez.", 409)
    db.commit()
    db.refresh(doc)
    return view(doc)
