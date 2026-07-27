import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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

// Page Sessions, pixel-identique au preview (liste .session-row + detail .msg).
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
  const openSession = sessions.find((s) => s.id === openId);
  const messages = messagesQuery.data ?? [];

  return (
    <>
      <div className="page-header">
        <h1>{t("sessions.title")}</h1>
        <p>{t("sessions.subtitle")}</p>
      </div>

      <div className="grid-2">
        <div className="card">
          <h2 className="card-title">{t("sessions.title")}</h2>
          {sessions.length === 0 ? (
            <div className="empty-state">{t("sessions.empty")}</div>
          ) : (
            <div className="session-list">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className={`session-row${s.id === openId ? " active" : ""}`}
                  onClick={() => setOpenId(s.id)}
                >
                  <div>
                    <div className="session-name">{s.title || s.id}</div>
                    <div className="session-meta">{formatDate(s.created_at)}</div>
                  </div>
                  <div className="row">
                    <span className="badge">{s.lang}</span>
                    <button
                      type="button"
                      className="btn ghost small"
                      disabled={deleteMutation.isPending}
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteMutation.mutate(s.id);
                      }}
                    >
                      {t("sessions.delete")}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="card-title">
            {openSession
              ? openSession.title || openSession.id
              : t("sessions.selectOne")}
          </h2>
          {!openId ? (
            <div className="empty-state">{t("sessions.none")}</div>
          ) : messages.length === 0 ? (
            <div className="empty-state">{t("sessions.noMessages")}</div>
          ) : (
            messages.map((m) => (
              <div key={m.id} className={`msg ${m.role}`}>
                <div className="msg-role">{m.role}</div>
                <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
                {m.citations.length > 0 ? (
                  <div className="msg-citations">
                    {t("sessions.sources")} :{" "}
                    {m.citations.map((c) => `[${c.filename}]`).join(" ")}
                  </div>
                ) : null}
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
