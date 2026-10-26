import { Button, Spinner, Textarea, cn } from "@internal/ui";
import { useMutation } from "@tanstack/react-query";
import { Bot, Send, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { errorText } from "../../lib/api";
import { assistantApi } from "../../lib/flowApi";
import { useEditorStore } from "../../stores/editorStore";
import type { ChatMessage } from "../../types/flow";
import { AttachButton, DocumentChips, useAttachFile } from "./AssistantAttachments";
import { DemoButton, DemoPicker, useDemoActive } from "./DemoPicker";

// Le backend borne l'historique ; on n'envoie que la fin de la conversation.
const HISTORY_SENT = 40;

export function AssistantPanel() {
  const { t } = useTranslation();
  const { graph, messages, documents, pushMessage, applyAssistant } = useEditorStore();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  // isPending n'est visible qu'au rendu suivant : verrou synchrone contre le double envoi.
  const inFlight = useRef(false);
  const { attachFiles, isPending: uploading } = useAttachFile(setError);
  const demoActive = useDemoActive();
  const [demoOpen, setDemoOpen] = useState(false);

  const loadDemo = (files: File[], prompt: string) => {
    setDemoOpen(false);
    if (prompt) setDraft(prompt);
    if (files.length > 0) void attachFiles(files);
  };

  const chat = useMutation({
    mutationFn: (history: ChatMessage[]) => assistantApi.chat(history.slice(-HISTORY_SENT), graph, documents),
    onMutate: () => setError(null),
    onSuccess: (reply) => applyAssistant(reply),
    onError: (e: unknown) => setError(errorText(e)),
    onSettled: () => {
      inFlight.current = false;
    },
  });

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages.length, chat.isPending, uploading]);

  const busy = chat.isPending || uploading;

  const send = (text: string) => {
    const content = text.trim();
    if (!content || inFlight.current || uploading) return;
    inFlight.current = true;
    const message: ChatMessage = { role: "user", content };
    pushMessage(message);
    setDraft("");
    chat.mutate([...messages, message]);
  };

  return (
    <div
      className={cn("flex h-full min-h-0 flex-col gap-3 rounded", dragging && "ring-2 ring-brand-blue-light")}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (!busy) void attachFiles(e.dataTransfer.files);
      }}
    >
      <div
        ref={listRef}
        className="flex min-h-[8rem] flex-1 flex-col gap-3 overflow-y-auto rounded border p-3"
        data-testid="assistant-messages"
        aria-live="polite"
      >
        {messages.length === 0 && <p className="text-fg-dim">{t("editor.assistant.welcome")}</p>}
        {messages.map((m, i) => (
          <div key={i} className={cn("flex gap-2", m.role === "user" ? "flex-row-reverse text-right" : "")}>
            <span className="mt-1 shrink-0 text-fg-dim">
              {m.role === "user" ? <User size={16} aria-hidden /> : <Bot size={16} aria-hidden />}
            </span>
            <div
              className={cn(
                "max-w-[85%] whitespace-pre-wrap rounded px-3 py-2",
                m.role === "user" ? "bg-card text-fg" : "bg-bg-2 text-fg",
              )}
            >
              {m.content}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex items-center gap-2 text-fg-dim">
            <Spinner size="sm" /> {uploading ? t("editor.assistant.uploading") : t("editor.assistant.thinking")}
          </div>
        )}
      </div>

      <DocumentChips />

      {demoActive && demoOpen && <DemoPicker disabled={busy} onLoad={loadDemo} />}

      <Textarea
        className="shrink-0"
        rows={4}
        maxLength={20000}
        value={draft}
        placeholder={graph ? t("editor.assistant.placeholderEdit") : t("editor.assistant.placeholder")}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            send(draft);
          }
        }}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <AttachButton disabled={chat.isPending} pending={uploading} onFiles={attachFiles} />
          {demoActive && <DemoButton open={demoOpen} disabled={busy} onToggle={() => setDemoOpen((o) => !o)} />}
          <span className="text-fg-dim">{t("editor.assistant.hint")}</span>
        </div>
        <Button disabled={busy || !draft.trim()} onClick={() => send(draft)}>
          <Send size={14} aria-hidden /> {t("editor.assistant.send")}
        </Button>
      </div>

      {error && (
        <div className="text-danger" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
