import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "../components/PageHeader";
import { resources, type ChatSession } from "../lib/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

type Message = { role: "user" | "assistant"; content: string };

function SessionList({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDelete,
}: {
  sessions: ChatSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}) {
  const { t } = useTranslation();
  const [armedId, setArmedId] = useState<string | null>(null);
  const [armTimer, setArmTimer] = useState<ReturnType<typeof setTimeout> | null>(null);

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (armedId === id) {
      if (armTimer) clearTimeout(armTimer);
      setArmedId(null);
      onDelete(id);
    } else {
      if (armTimer) clearTimeout(armTimer);
      setArmedId(id);
      const timer = setTimeout(() => setArmedId(null), 3000);
      setArmTimer(timer);
    }
  };

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r bg-bg-2">
      <div className="flex items-center justify-between border-b px-3 py-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-fg-dim">
          {t("chat.sessions")}
        </span>
        <button
          type="button"
          onClick={onNew}
          title={t("chat.newSession")}
          className="rounded p-1 text-fg-dim transition-colors hover:text-fg"
        >
          ＋
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 && (
          <p className="px-3 py-4 text-xs text-fg-dim">{t("chat.noSessions")}</p>
        )}
        {sessions.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => onSelect(s.id)}
            className={[
              "group flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm transition-colors",
              activeId === s.id ? "bg-brand/20 text-fg" : "text-fg-dim hover:bg-card-hover hover:text-fg",
            ].join(" ")}
          >
            <span className="flex-1 truncate">{s.title}</span>
            <span
              onClick={(e) => handleDelete(e, s.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && handleDelete(e as unknown as React.MouseEvent, s.id)}
              className={[
                "shrink-0 rounded px-1 text-xs opacity-0 transition-opacity group-hover:opacity-100",
                armedId === s.id ? "bg-red-600 text-white opacity-100" : "text-red-400",
              ].join(" ")}
            >
              ×
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  const { t } = useTranslation();
  const isUser = msg.role === "user";
  return (
    <div className={["flex gap-3", isUser ? "justify-end" : "justify-start"].join(" ")}>
      {!isUser && (
        <span className="mt-1 shrink-0 text-xs font-semibold text-brand-blue-light">
          {t("chat.assistant")}
        </span>
      )}
      <div
        className={[
          "max-w-[70%] rounded-lg px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
          isUser ? "bg-brand text-fg" : "bg-card text-fg shadow-card",
        ].join(" ")}
      >
        {msg.content}
      </div>
      {isUser && (
        <span className="mt-1 shrink-0 text-xs font-semibold text-fg-dim">
          {t("chat.you")}
        </span>
      )}
    </div>
  );
}

export function Chat() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: sessions = [] } = useQuery({
    queryKey: ["chat", "sessions"],
    queryFn: resources.chat.sessions,
  });

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: resources.projects.list,
  });

  const deleteSession = useMutation({
    mutationFn: resources.chat.deleteSession,
    onSuccess: (_, id) => {
      void qc.invalidateQueries({ queryKey: ["chat", "sessions"] });
      if (sessionId === id) {
        setSessionId(null);
        setMessages([]);
      }
    },
  });

  const loadMessages = async (sid: string) => {
    try {
      const msgs = await resources.chat.messages(sid);
      setMessages(
        msgs.map((m) => ({ role: m.role as "user" | "assistant", content: m.content })),
      );
    } catch {
      setMessages([]);
    }
  };

  const handleSelectSession = (sid: string) => {
    setSessionId(sid);
    void loadMessages(sid);
  };

  const handleNewSession = () => {
    setSessionId(null);
    setMessages([]);
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    const q = question.trim();
    if (!q || streaming) return;
    setQuestion("");
    setStreamError(null);
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setStreaming(true);

    let assistantContent = "";
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const response = await fetch(`${BASE_URL}/chat/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          project_ids: [],
          session_id: sessionId ?? undefined,
          lang: "fr",
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let currentEvent = "";
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const data = line.slice(6).trim();
            if (!data) continue;

            if (currentEvent === "session") {
              try {
                const parsed = JSON.parse(data) as { session_id: string };
                setSessionId(parsed.session_id);
                void qc.invalidateQueries({ queryKey: ["chat", "sessions"] });
              } catch { /* ignore */ }
              currentEvent = "";
            } else if (currentEvent === "done" || data === "[DONE]") {
              break;
            } else if (currentEvent === "error") {
              try {
                const parsed = JSON.parse(data) as { message: string };
                setStreamError(parsed.message);
              } catch {
                setStreamError(t("chat.errorStream"));
              }
              break;
            } else {
              assistantContent += data;
              setMessages((prev) => {
                const next = [...prev];
                next[next.length - 1] = { role: "assistant", content: assistantContent };
                return next;
              });
              currentEvent = "";
            }
          }
        }
      }
    } catch {
      setStreamError(t("chat.errorStream"));
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  return (
    <div className="flex h-full">
      <SessionList
        sessions={sessions}
        activeId={sessionId}
        onSelect={handleSelectSession}
        onNew={handleNewSession}
        onDelete={(id) => deleteSession.mutate(id)}
      />

      <div className="flex flex-1 flex-col">
        <PageHeader
          title={t("routes.chat.title")}
          subtitle={
            projects.length > 0
              ? `${projects.length} projet(s) disponible(s)`
              : t("routes.chat.subtitle")
          }
        />

        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.length === 0 && (
              <p className="text-center text-sm text-fg-dim">{t("common.empty")}</p>
            )}
            {messages.map((msg, i) => (
              <MessageBubble key={i} msg={msg} />
            ))}
            {streamError && (
              <p className="text-center text-sm text-red-400">{streamError}</p>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="border-t px-6 py-4">
          <div className="mx-auto flex max-w-3xl gap-3">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t("chat.placeholder")}
              rows={2}
              disabled={streaming}
              className="flex-1 resize-none rounded-lg border bg-bg px-3 py-2 text-sm text-fg placeholder-fg-dim focus:outline-none focus:ring-2 focus:ring-brand-blue-light disabled:opacity-50"
            />
            <button
              type="button"
              onClick={() => void send()}
              disabled={streaming || !question.trim()}
              className="self-end rounded-lg bg-brand px-5 py-2 text-sm font-medium text-fg shadow-card transition-colors hover:bg-brand-blue-light disabled:opacity-50"
            >
              {streaming ? t("chat.sending") : t("chat.send")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
