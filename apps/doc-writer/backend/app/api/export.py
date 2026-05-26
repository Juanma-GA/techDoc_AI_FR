"""Route /api/v1/sessions/{id}/export?format=md|docx|pdf|pptx.

Charge le dernier message assistant de la session et le renvoie tel quel
(md), converti en .docx via python-docx, en .pdf via reportlab, ou en
.pptx en remplissant le template attache a la session (cf. `template_doc_id`).

Tous les exports sont best-effort : pas de fidelite typographique parfaite.
Le destinataire peut affiner dans Word / Acrobat / PowerPoint.
"""

from __future__ import annotations

import io
import json
import logging
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.mistral_client import MistralClient, MistralError
from app.core.pptx_llm_analysis import split_zones
from app.core.pptx_template import Zone, fill_zones
from app.db.models import Document, Message, Session as SessionRow
from app.db.session import get_db


log = logging.getLogger("doc_writer.export")

router = APIRouter(tags=["export"])


VALID_FORMATS = {"md", "docx", "pdf", "pptx"}
MEDIA_TYPES = {
    "md":   "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf":  "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def _safe_filename(title: str, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._\- ]+", "_", title or "session").strip(" ._") or "session"
    return f"{base[:80]}.{ext}"


def _last_assistant_content(db: Session, session_id: uuid.UUID) -> tuple[Optional[str], str]:
    """Retourne (titre_session, contenu_assistant) ou ('', '') si rien."""
    session = db.get(SessionRow, session_id)
    if session is None:
        raise AppError(
            "SESSION_NOT_FOUND",
            "Session introuvable.",
            status_code=404,
            detail={"id": str(session_id)},
        )
    msg = db.scalar(
        select(Message)
        .where(Message.session_id == session_id, Message.role == "assistant")
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    if msg is None:
        return session.title or "", ""
    return session.title or "", msg.content or ""


def _markdown_to_docx_bytes(markdown_text: str) -> bytes:
    """Parsing markdown ligne-a-ligne, best-effort."""
    from docx import Document  # type: ignore[import-untyped]

    doc = Document()
    lines = (markdown_text or "").splitlines()
    in_table = False
    table_rows: list[list[str]] = []

    def _flush_table() -> None:
        nonlocal in_table, table_rows
        if not table_rows:
            in_table = False
            return
        # Premiere ligne = entete, deuxieme = separateur (---), reste = data.
        header = table_rows[0]
        data_rows = [r for r in table_rows[2:] if r]
        if not header:
            in_table = False
            table_rows = []
            return
        t = doc.add_table(rows=1 + len(data_rows), cols=len(header))
        t.style = "Light Grid"
        for j, h in enumerate(header):
            t.cell(0, j).text = h
        for i, row in enumerate(data_rows, start=1):
            for j in range(len(header)):
                t.cell(i, j).text = row[j] if j < len(row) else ""
        in_table = False
        table_rows = []

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("|") and "|" in line[1:]:
            in_table = True
            cells = [c.strip() for c in line.strip("|").split("|")]
            table_rows.append(cells)
            continue
        if in_table:
            _flush_table()

        if not line.strip():
            doc.add_paragraph("")
            continue
        if line.startswith("### "):
            doc.add_heading(line[4:].strip(), level=3)
        elif line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith("# "):
            doc.add_heading(line[2:].strip(), level=1)
        elif line.startswith("- ") or line.startswith("* "):
            doc.add_paragraph(line[2:].strip(), style="List Bullet")
        elif re.match(r"^\d+\.\s", line):
            doc.add_paragraph(re.sub(r"^\d+\.\s+", "", line), style="List Number")
        else:
            doc.add_paragraph(line)
    if in_table:
        _flush_table()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _markdown_to_pdf_bytes(markdown_text: str) -> bytes:
    """Rendu PDF via reportlab Platypus, best-effort."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        ListFlowable,
        ListItem,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.lib import colors

    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40,
    )
    story: list = []
    lines = (markdown_text or "").splitlines()
    bullets: list[str] = []

    def _flush_bullets() -> None:
        nonlocal bullets
        if not bullets:
            return
        items = [ListItem(Paragraph(b, styles["BodyText"])) for b in bullets]
        story.append(ListFlowable(items, bulletType="bullet"))
        bullets = []

    table_rows: list[list[str]] = []
    in_table = False

    def _flush_table() -> None:
        nonlocal in_table, table_rows
        if not table_rows:
            in_table = False
            return
        data = [table_rows[0]] + [r for r in table_rows[2:] if r]
        t = Table(data, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))
        in_table = False
        table_rows = []

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("|") and "|" in line[1:]:
            _flush_bullets()
            in_table = True
            cells = [c.strip() for c in line.strip("|").split("|")]
            table_rows.append(cells)
            continue
        if in_table:
            _flush_table()

        if not line.strip():
            _flush_bullets()
            story.append(Spacer(1, 6))
            continue
        if line.startswith("### "):
            _flush_bullets()
            story.append(Paragraph(line[4:], styles["Heading3"]))
        elif line.startswith("## "):
            _flush_bullets()
            story.append(Paragraph(line[3:], styles["Heading2"]))
        elif line.startswith("# "):
            _flush_bullets()
            story.append(Paragraph(line[2:], styles["Heading1"]))
        elif line.startswith("- ") or line.startswith("* "):
            bullets.append(line[2:].strip())
        else:
            _flush_bullets()
            # Escape les chevrons HTML qui crashent reportlab.
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe, styles["BodyText"]))
    _flush_bullets()
    if in_table:
        _flush_table()

    doc.build(story)
    return buf.getvalue()


_PPTX_SYSTEM = (
    "Tu es un assistant de remplissage de template PowerPoint. "
    "On te fournit (a) un contenu source en markdown produit par un autre LLM, "
    "et (b) une liste de zones a remplir dans un .pptx. Chaque zone a un id, "
    "un type (`placeholder` pour les marqueurs explicites {{cle}}, `xxx` pour "
    "les zones libres marquees XXX, `empty_cell` pour une cellule de table "
    "vide identifiee par ses headers de ligne/colonne), un titre de slide, un "
    "label semantique qui indique le sujet attendu, et une location ('Slide N "
    "/ Tableau M / Ligne R') qui aide a distinguer des zones ayant le meme "
    "label dans des tables paralleles. "
    "Tu dois renvoyer STRICTEMENT un objet JSON dont les cles sont EXACTEMENT "
    "les ids fournis, et les valeurs sont du texte brut (pas de markdown, "
    "pas de #, pas de **) destine a etre injecte dans le .pptx. Pour chaque "
    "zone, redige un contenu adapte au label et au titre de la slide, en "
    "tirant la matiere du contenu source. Quand plusieurs zones partagent le "
    "meme label (tables paralleles type 'Experience 1' / 'Experience 2'), "
    "utilise leur location pour les differencier : si la source contient "
    "plusieurs occurrences, attribue chacune a une location distincte. "
    "Tu peux utiliser des sauts de ligne (\\n) dans les valeurs. Si une zone "
    "n'a pas de matiere pertinente dans la source, mets une chaine vide."
)


def _build_zone_mapping(
    markdown_text: str,
    zones: list[Zone],
    mistral: MistralClient,
) -> dict[str, str]:
    """Appelle Mistral en mode JSON pour mapper chaque zone a un contenu."""
    descriptors = [
        {
            "id": z.id,
            "kind": z.kind,
            "slide_index": z.slide_index,
            "slide_title": z.slide_title,
            "label": z.label,
            "location": z.location,
        }
        for z in zones
    ]
    user_msg = (
        f"Contenu source :\n```\n{markdown_text}\n```\n\n"
        f"Zones a remplir :\n{json.dumps(descriptors, ensure_ascii=False)}\n\n"
        "Renvoie un JSON {id: contenu}."
    )
    raw = mistral.chat_json(
        messages=[
            {"role": "system", "content": _PPTX_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
    )
    out: dict[str, str] = {}
    for z in zones:
        val = raw.get(z.id, "")
        if val is None:
            out[z.id] = ""
        elif isinstance(val, str):
            out[z.id] = val
        else:
            out[z.id] = str(val)
    return out


def _load_zones_for_template(db: Session, template: Document) -> list[Zone]:
    """Charge les zones depuis le cache de `Document.extracted_text`. Si pas
    de cache (ou cache invalide), recalcule via la pipeline (regex + LLM)."""
    from app.api.documents import (
        _compute_zones,
        _read_zones_cache,
        _write_zones_cache,
    )

    cached, _llm_used = _read_zones_cache(template)
    if cached is not None:
        return [
            Zone(
                id=z["id"],
                kind=z["kind"],
                slide_index=z["slide_index"],
                slide_title=z["slide_title"],
                label=z["label"],
                location=z["location"],
                target=z.get("target", ""),
            )
            for z in cached
        ]
    zones, llm_used = _compute_zones(template, db)
    _write_zones_cache(template, zones, llm_used, db)
    return zones


def _pptx_from_session(
    db: Session,
    session_id: uuid.UUID,
    markdown_text: str,
) -> bytes:
    session = db.get(SessionRow, session_id)
    if session is None or session.template_doc_id is None:
        raise AppError(
            "TEMPLATE_REQUIRED",
            "Cette session n'a pas de template .pptx attache. Selectionne un "
            "template avant l'export PPTX.",
            status_code=400,
            detail={"session_id": str(session_id)},
        )
    template = db.get(Document, session.template_doc_id)
    if template is None:
        raise AppError(
            "TEMPLATE_NOT_FOUND",
            "Le document template n'existe plus.",
            status_code=404,
            detail={"template_doc_id": str(session.template_doc_id)},
        )
    if not template.filename.lower().endswith(".pptx"):
        raise AppError(
            "UNSUPPORTED_TEMPLATE",
            "Seul le format .pptx est supporte comme template d'export.",
            status_code=400,
            detail={"filename": template.filename},
        )

    zones = _load_zones_for_template(db, template)
    if not zones:
        raise AppError(
            "NO_ZONES_FOUND",
            "Aucune zone a remplir n'a ete detectee dans le template (ni "
            "marqueur {{cle}}, ni zone XXX, ni zone identifiee par Mistral). "
            "Verifie que ton .pptx contient des zones a remplir.",
            status_code=400,
            detail={"template": template.filename},
        )

    try:
        mistral = MistralClient.from_db(db)
    except MistralError as e:
        raise AppError("MISTRAL_NOT_CONFIGURED", str(e), status_code=400) from e

    try:
        mapping = _build_zone_mapping(markdown_text, zones, mistral)
    except MistralError as e:
        raise AppError(
            "MAPPING_FAILED",
            f"Mistral n'a pas renvoye un mapping JSON exploitable : {e}",
            status_code=502,
        ) from e

    _regex_zones, llm_zones = split_zones(zones)
    return fill_zones(template.storage_path, mapping, llm_zones=llm_zones)


@router.get("/sessions/{session_id}/export")
def export_session(
    session_id: uuid.UUID,
    format: str = Query(default="md"),
    filename: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    """Export du dernier message assistant.

    Le client peut imposer un nom via `?filename=mon-rapport` (sans extension,
    elle est ajoutee selon `format`). Caracteres non sains remplaces par `_`.
    Si absent, on prend le titre de la session.
    """
    if format not in VALID_FORMATS:
        raise AppError(
            "INVALID_FORMAT",
            f"format doit etre dans {sorted(VALID_FORMATS)}",
            status_code=400,
            detail={"format": format},
        )

    title, content = _last_assistant_content(db, session_id)
    if not content.strip():
        raise AppError(
            "NOTHING_TO_EXPORT",
            "Aucun contenu assistant a exporter pour cette session.",
            status_code=404,
            detail={"session_id": str(session_id)},
        )

    # Si le client passe un filename, il prime ; sinon fallback sur le titre.
    base_name = (filename or "").strip() or (title or str(session_id))
    out_filename = _safe_filename(base_name, format)
    headers = {"Content-Disposition": f'attachment; filename="{out_filename}"'}

    if format == "md":
        return Response(
            content=content,
            media_type=MEDIA_TYPES["md"],
            headers=headers,
        )

    try:
        if format == "docx":
            data = _markdown_to_docx_bytes(content)
        elif format == "pptx":
            data = _pptx_from_session(db, session_id, content)
        else:  # pdf
            data = _markdown_to_pdf_bytes(content)
    except AppError:
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("export %s failed", format)
        raise AppError(
            "EXPORT_FAILED",
            f"Conversion {format} a echoue : {type(e).__name__}: {e}",
            status_code=500,
        ) from e

    return StreamingResponse(
        io.BytesIO(data),
        media_type=MEDIA_TYPES[format],
        headers=headers,
    )
