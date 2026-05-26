import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  MarkdownView,
  Spinner,
} from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiClientError,
  sessionsApi,
  type MessageDto,
  type SessionDto,
} from "../lib/api";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function Sessions() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [openId, setOpenId] = useState<string | null>(null);

  const sessionsQuery = useQuery<SessionDto[], ApiClientError>({
    queryKey: ["sessions"],
    queryFn: sessionsApi.list,
  });

  const messagesQuery = useQuery<MessageDto[], ApiClientError>({
    queryKey: ["sessions", openId, "messages"],
    queryFn: () => sessionsApi.messages(openId as string),
    enabled: openId !== null,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => sessionsApi.remove(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["sessions"] });
      setOpenId(null);
    },
  });

  const sessions = sessionsQuery.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("sessions.title")}</h1>
        <p className="text-fg-dim">{t("sessions.subtitle")}</p>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("sessions.title")}</CardTitle>
          </CardHeader>
          <CardContent>
            {sessionsQuery.isLoading ? (
              <Spinner />
            ) : sessions.length === 0 ? (
              <EmptyState title={t("sessions.empty")} />
            ) : (
              <ul className="flex flex-col gap-2">
                {sessions.map((s) => (
                  <li
                    key={s.id}
                    className="flex items-center justify-between gap-2 rounded-sm border border-md bg-card p-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-fg">{s.title || s.id}</p>
                      <p className="text-xs text-fg-dim">
                        {t("sessions.createdAt")} {formatDate(s.created_at)}
                        {" · "}
                        {t("sessions.scope")}:{" "}
                        {s.scope_doc_ids.length === 0
                          ? "*"
                          : s.scope_doc_ids.length}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <Badge>{s.lang}</Badge>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => setOpenId(s.id)}
                      >
                        {t("sessions.open")}
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label={t("sessions.delete")}
                        onClick={() => deleteMutation.mutate(s.id)}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 size={14} aria-hidden="true" />
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>
              {openId
                ? sessions.find((s) => s.id === openId)?.title || openId
                : t("sessions.empty")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!openId ? (
              <p className="text-fg-dim">{t("sessions.empty")}</p>
            ) : messagesQuery.isLoading ? (
              <Spinner />
            ) : (
              <div className="flex flex-col gap-3">
                {(messagesQuery.data ?? []).map((m) => (
                  <div
                    key={m.id}
                    className={
                      m.role === "user"
                        ? "rounded-sm border border-md bg-bg-2 p-3 text-fg"
                        : "rounded-sm border border-md bg-card p-3 text-fg"
                    }
                  >
                    <p className="label mb-1">{m.role}</p>
                    {m.role === "assistant" ? (
                      <MarkdownView content={m.content} />
                    ) : (
                      <p className="whitespace-pre-wrap">{m.content}</p>
                    )}
                    {m.citations.length > 0 ? (
                      <p className="mt-2 text-xs text-fg-dim">
                        {t("generate.citations")}:{" "}
                        {m.citations
                          .map((c) => `[${c.filename}]`)
                          .join(" ")}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
