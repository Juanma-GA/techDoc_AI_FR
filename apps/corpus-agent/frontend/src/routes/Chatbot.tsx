import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ProjectSlicer } from "../components/ProjectSlicer";
import { useSseChat } from "../hooks/useSseChat";
import { chatApi, projectsApi } from "../lib/api";
import { useChatStore } from "../stores/useChatStore";
import type { ChatSessionOut, ProjectOut } from "../lib/types";

const SUGGESTION_KEYS = ["chatbot.suggestion1", "chatbot.suggestion2", "chatbot.suggestion3"] as const;

export function Chatbot() {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language || "fr").slice(0, 2);
  const qc = useQueryClient();
  const [question, setQuestion] = useState("");
  const messagesRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const { scopeProjectIds, currentSessionId, pendingNew, messages, streaming } = useChatStore();
  const store = useChatStore();
  const { send } = useSseChat();

  const projectsQuery = useQuery<ProjectOut[]>({ queryKey: ["projects"], queryFn: projectsApi.list });
  const sessionsQuery = useQuery<ChatSessionOut[]>({ queryKey: ["chat-sessions"], queryFn: chatApi.sessions });
  const projects = projectsQuery.data ?? [];
  const sessions = sessionsQuery.data ?? [];

  useEffect(() => {
    if (messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [question]);

  const scopeLabel = () => {
    if (scopeProjectIds.length === 0) return t("chatbot.scopeAll");
    const names = scopeProjectIds.map((id) => {
      const p = projects.find((x) => x.id === id);
      return p ? p.name : id.slice(0, 8);
    });
    const prefix = scopeProjectIds.length === 1 ? t("chatbot.scopeOne") : t("chatbot.scopeMulti");
    return `${prefix} : ${names.join(", ")}`;
  };

  const scopeBadge = (ids: string[]) => {
    if (!ids.length) return <span className="badge info">{t("chatbot.scopeAll")}</span>;
    if (ids.length === 1) {
      const first = ids[0] ?? "";
      const p = projects.find((x) => x.id === first);
      return <span className="badge default">{p?.name ?? first.slice(0, 8)}</span>;
    }
    return <span className="badge default">{ids.length} {t("chatbot.scopeProjects")}</span>;
  };

  const pickSession = async (s: ChatSessionOut) => {
    const msgs = await chatApi.messages(s.id);
    store.selectSession(
      s.id,
      msgs.filter((m) => m.role === "user" || m.role === "assistant").map((m) => ({ role: m.role as "user" | "assistant", content: m.content })),
    );
  };
  const deleteSession = async (id: string) => {
    await chatApi.removeSession(id);
    if (currentSessionId === id) store.reset();
    void qc.invalidateQueries({ queryKey: ["chat-sessions"] });
  };

  const onSend = () => {
    const q = question.trim();
    if (!q) return;
    setQuestion("");
    send(q, scopeProjectIds, lang);
  };

  return (
    <>
      <div className="page-header">
        <h1>{t("nav.chatbot")}</h1>
        <p>{t("page.chatbot")}</p>
      </div>

      <div className="chat-layout">
        <div className="card chat-sessions">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="card-title" style={{ margin: 0 }}>{t("chatbot.sessions")}</span>
            <button type="button" className="btn ghost small" onClick={() => store.startNew()}>{t("chatbot.new")}</button>
          </div>
          <div className="session-list" style={{ marginTop: 10 }}>
            {pendingNew && !currentSessionId && (
              <div className="session-row active">
                <div className="session-row-main">
                  <div className="session-row-title">{t("chatbot.newSessionLabel")}</div>
                  <div className="session-row-badges">{scopeBadge(scopeProjectIds)}</div>
                </div>
              </div>
            )}
            {sessions.map((s) => (
              <div key={s.id} className={`session-row${s.id === currentSessionId ? " active" : ""}`} onClick={() => void pickSession(s)}>
                <div className="session-row-main">
                  <div className="session-row-title">{s.title}</div>
                  <div className="session-row-badges">{scopeBadge(s.scope_project_ids)}</div>
                </div>
                <button type="button" className="btn ghost small" title={t("common.delete")} aria-label={t("common.delete")} onClick={(e) => { e.stopPropagation(); void deleteSession(s.id); }}>×</button>
              </div>
            ))}
            {!sessions.length && !pendingNew && <div className="empty-state">—</div>}
          </div>
        </div>

        <div className="card chat-thread">
          <div className="chat-scope-bar">
            <span className="label">{t("chatbot.selectProject")}</span>
            <ProjectSlicer projects={projects} value={scopeProjectIds} onChange={store.setScope} />
            <span className="label">{scopeLabel()}</span>
          </div>
          <div className="chat-messages" ref={messagesRef} aria-live="polite">
            {messages.length === 0 && (
              <div className="chat-empty">
                <div className="chat-empty-title">{t("chatbot.emptyTitle")}</div>
                <div className="label">{t("chatbot.emptyHint")}</div>
                <div className="chat-suggestions">
                  {SUGGESTION_KEYS.map((key) => (
                    <button key={key} type="button" className="chat-suggestion" disabled={streaming} onClick={() => send(t(key), scopeProjectIds, lang)}>
                      {t(key)}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => {
              const waiting = m.role === "assistant" && streaming && i === messages.length - 1 && m.content === "";
              return (
                <div className={`chat-msg-wrap ${m.role}`} key={i}>
                  <span className="label">{m.role === "user" ? t("chatbot.you") : t("chatbot.assistant")}</span>
                  <div className={`chat-msg ${m.role}`}>
                    {waiting ? (
                      <span className="chat-typing" role="status" aria-label={t("chatbot.thinking")}><span /><span /><span /></span>
                    ) : (
                      m.content
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="chat-composer">
            <div className="chat-input">
              <textarea
                ref={inputRef}
                rows={1}
                value={question}
                placeholder={t("chatbot.placeholder")}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (!streaming) onSend();
                  }
                }}
              />
              <button type="button" className="btn primary" onClick={onSend} disabled={streaming || !question.trim()}>{t("chatbot.send")}</button>
            </div>
            <div className="label chat-hint">{t("chatbot.inputHint")}</div>
          </div>
        </div>
      </div>
    </>
  );
}
