"""RAG context builder + streaming answer generator. Multi-scope (1, plusieurs ou tous projets)."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.indexer import search_similar
from app.core.mistral_client import MistralClient
from app.db.models import Anomaly, ChatMessage, ChatSession, Project


log = logging.getLogger("ftm.chat")


SYSTEM_PROMPT_FR = (
    "Tu es l'assistant FTM Agent : tu réponds à des questions sur des fiches de tâches de "
    "maintenance (FTM) et les anomalies détectées dans un ou plusieurs projets. "
    "Tu réponds TOUJOURS en français, de façon concise et factuelle. "
    "Tu cites tes sources au format [nom_fichier] entre crochets après chaque affirmation "
    "qui s'appuie sur un extrait. "
    "Si l'information n'est pas dans le contexte fourni, dis-le clairement au lieu d'inventer."
)
SYSTEM_PROMPT_EN = (
    "You are the FTM Agent assistant: you answer questions about Maintenance Task Files (FTMs) "
    "and anomalies detected in one or several projects. You ALWAYS reply in English, concisely "
    "and factually. You cite sources in the format [file_name] in brackets after each statement "
    "based on a snippet. If the information is not in the provided context, say so explicitly "
    "instead of making it up."
)
SYSTEM_PROMPT_ES = (
    "Eres el asistente FTM Agent: respondes a preguntas sobre fichas de tareas de mantenimiento "
    "(FTM) y las anomalías detectadas en uno o varios proyectos. Respondes SIEMPRE en español, "
    "de manera concisa y factual. Citas tus fuentes en el formato [nombre_archivo] entre "
    "corchetes. Si la información no está en el contexto, dilo claramente en lugar de inventar."
)


def system_prompt(lang: str) -> str:
    return {"en": SYSTEM_PROMPT_EN, "es": SYSTEM_PROMPT_ES}.get(lang, SYSTEM_PROMPT_FR)


def _scope_label(projects: list[Project]) -> str:
    if not projects:
        return "tous les projets"
    if len(projects) == 1:
        return f"projet « {projects[0].name} »"
    names = ", ".join(f"« {p.name} »" for p in projects)
    return f"{len(projects)} projets ({names})"


def build_context_messages(
    db: Session,
    projects: list[Project],
    question: str,
    mistral: MistralClient,
    history: Optional[list[dict[str, Any]]] = None,
    k: int = 6,
    lang: str = "fr",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """`projects = []` → recherche sur tous les projets de la DB.
    `[p1]` → un projet, `[p1, p2]` → plusieurs."""
    project_ids = [p.id for p in projects]
    # La recherche RAG depend de l'API embeddings. Si elle echoue (modele
    # d'embedding mal configure, endpoint indisponible), on ne fait PAS echouer
    # tout le chat : on degrade en repondant a partir des seules anomalies.
    rag_error: Optional[str] = None
    try:
        hits = search_similar(db, project_ids if project_ids else None, question, mistral, k=k)
    except Exception as e:  # noqa: BLE001
        hits = []
        rag_error = f"{type(e).__name__}: {e}"
        log.warning("RAG search indisponible, chat en mode degrade : %s", e)
    blocks = [f"[{h['filename']}] (extrait {i + 1})\n{h['text']}" for i, h in enumerate(hits)]
    citations = [{"chunk_id": h["chunk_id"], "filename": h["filename"], "score": h["score"]} for h in hits]

    # Filtres anomalies — None / [] = pas de filtre.
    anomaly_filter = Anomaly.project_id.in_(project_ids) if project_ids else None

    def _count(*extra_filters):
        stmt = select(func.count(Anomaly.id))
        if anomaly_filter is not None:
            stmt = stmt.where(anomaly_filter)
        for f in extra_filters:
            stmt = stmt.where(f)
        return db.scalar(stmt) or 0

    total_open = _count(Anomaly.status == "open")
    total_all = _count()

    # Repartition sur le workflow d'etat (open / acknowledged / fixed / rejected)
    # — donne a l'assistant la visibilite sur le traitement des anomalies.
    stmt_by_status = select(Anomaly.status, func.count(Anomaly.id))
    if anomaly_filter is not None:
        stmt_by_status = stmt_by_status.where(anomaly_filter)
    by_status = dict(db.execute(stmt_by_status.group_by(Anomaly.status)).all())

    # Anomalies a traiter : ouvertes + acquittees. `selectinload` du fichier
    # pour eviter le N+1 lors du rendu des details (fichier / emplacement).
    stmt_open = (
        select(Anomaly)
        .where(Anomaly.status.in_(("open", "acknowledged")))
        .options(selectinload(Anomaly.file_version))
    )
    if anomaly_filter is not None:
        stmt_open = stmt_open.where(anomaly_filter)
    open_anomalies = list(db.scalars(
        stmt_open.order_by(Anomaly.severity.desc(), Anomaly.created_at.desc()).limit(50)
    ))

    # Anomalies deja traitees (corrigees / refusees) : permet de repondre sur
    # le suivi et la maniere dont une anomalie a ete close.
    stmt_done = (
        select(Anomaly)
        .where(Anomaly.status.in_(("fixed", "rejected")))
        .options(selectinload(Anomaly.file_version))
    )
    if anomaly_filter is not None:
        stmt_done = stmt_done.where(anomaly_filter)
    done_anomalies = list(db.scalars(
        stmt_done.order_by(Anomaly.resolved_at.desc()).limit(20)
    ))

    stmt_by_type = select(Anomaly.type, func.count(Anomaly.id)).where(Anomaly.status == "open")
    if anomaly_filter is not None:
        stmt_by_type = stmt_by_type.where(anomaly_filter)
    by_type = dict(db.execute(stmt_by_type.group_by(Anomaly.type)).all())

    stmt_by_sev = select(Anomaly.severity, func.count(Anomaly.id)).where(Anomaly.status == "open")
    if anomaly_filter is not None:
        stmt_by_sev = stmt_by_sev.where(anomaly_filter)
    by_sev = dict(db.execute(stmt_by_sev.group_by(Anomaly.severity)).all())

    def _file_of(a: Anomaly) -> str:
        if a.file_version and a.file_version.filename:
            return a.file_version.filename
        return "fichier inconnu"

    def _open_line(a: Anomaly) -> str:
        line = (
            f"- [{a.type} | sévérité {a.severity} | statut {a.status} | "
            f"confiance {a.confidence}] fichier « {_file_of(a)} »"
        )
        if a.location:
            line += f", emplacement : {a.location}"
        line += f"\n  message : {a.message}"
        if a.suggestion:
            line += f"\n  suggestion : {a.suggestion}"
        return line

    def _done_line(a: Anomaly) -> str:
        resolved = a.resolved_at.date().isoformat() if a.resolved_at else "date inconnue"
        return (
            f"- [{a.type} | sévérité {a.severity} | statut {a.status}] "
            f"fichier « {_file_of(a)} » — {a.message} (résolue le {resolved})"
        )

    summary_lines = [_open_line(a) for a in open_anomalies] or ["(aucune anomalie a traiter)"]
    done_lines = [_done_line(a) for a in done_anomalies] or ["(aucune)"]
    by_status_str = ", ".join(f"{k}={v}" for k, v in by_status.items()) or "aucune"
    by_type_str = ", ".join(f"{k}={v}" for k, v in by_type.items()) or "aucune"
    by_sev_str = ", ".join(f"{k}={v}" for k, v in by_sev.items()) or "aucune"

    context_text = (
        f"Périmètre : {_scope_label(projects)}\n"
        f"Nombre total d'anomalies (tous statuts) : {total_all}\n"
        f"Nombre total d'anomalies ouvertes : {total_open}\n"
        f"Répartition par état (open/acknowledged/fixed/rejected) : {by_status_str}\n"
        f"Répartition par type (ouvertes) : {by_type_str}\n"
        f"Répartition par sévérité (ouvertes) : {by_sev_str}\n"
        f"Anomalies à traiter — ouvertes et acquittées (max 50) :\n" + "\n".join(summary_lines) + "\n\n"
        f"Anomalies déjà traitées — corrigées ou refusées (max 20) :\n" + "\n".join(done_lines) + "\n\n"
        f"Extraits FTM pertinents :\n\n"
        + (
            "\n\n---\n\n".join(blocks) if blocks
            else f"(recherche documentaire indisponible : {rag_error} — réponse basée "
                 "uniquement sur les anomalies ci-dessus)" if rag_error
            else "(aucun extrait trouvé)"
        )
    )

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt(lang)}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": f"Contexte :\n{context_text}\n\nQuestion : {question}"})
    return messages, citations


def get_or_create_session(
    db: Session,
    project_ids: list[uuid.UUID],
    session_id: Optional[uuid.UUID],
    question: str,
) -> ChatSession:
    """Crée (ou récupère) une session avec le scope donné."""
    if session_id:
        s = db.get(ChatSession, session_id)
        if s is not None:
            return s
    title = question[:60] + ("…" if len(question) > 60 else "")
    primary = project_ids[0] if project_ids else None
    s = ChatSession(
        project_id=primary,
        scope_project_ids=json.dumps([str(pid) for pid in project_ids]),
        title=title,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def history_for_session(db: Session, session: ChatSession, limit: int = 10) -> list[dict[str, Any]]:
    msgs = list(session.messages)[-limit:]
    return [{"role": m.role, "content": m.content} for m in msgs if m.role in ("user", "assistant")]


def session_scope_ids(session: ChatSession) -> list[uuid.UUID]:
    """Décode le champ JSON `scope_project_ids` en liste d'UUIDs."""
    try:
        raw = json.loads(session.scope_project_ids or "[]")
    except (json.JSONDecodeError, TypeError):
        return [session.project_id] if session.project_id else []
    out: list[uuid.UUID] = []
    for s in raw:
        try:
            out.append(uuid.UUID(s))
        except (ValueError, TypeError):
            continue
    return out


async def stream_answer(
    db: Session,
    projects: list[Project],
    session: ChatSession,
    question: str,
    mistral: MistralClient,
    lang: str = "fr",
) -> AsyncIterator[str]:
    history = history_for_session(db, session)
    messages, citations = build_context_messages(db, projects, question, mistral, history=history, lang=lang)

    db.add(ChatMessage(session_id=session.id, role="user", content=question, citations="[]"))
    db.commit()

    full_answer = ""
    async for delta in mistral.chat_stream(messages):
        full_answer += delta
        yield delta

    db.add(ChatMessage(
        session_id=session.id,
        role="assistant",
        content=full_answer,
        citations=json.dumps(citations, ensure_ascii=False),
    ))
    db.commit()
