import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { RichText } from "../components/RichText";
import { useDoubleClickConfirm } from "../hooks/useDoubleClickConfirm";
import { adminApi } from "../lib/api";
import { fmtBytes } from "../lib/format";
import type { AdminResetScope, AdminStatsOut } from "../lib/types";

function ResetButton({
  scope,
  labelKey,
  confirmKey,
  danger,
  onDone,
}: {
  scope: AdminResetScope;
  labelKey: string;
  confirmKey: string;
  danger?: boolean;
  onDone: (msg: string) => void;
}) {
  const { t } = useTranslation();
  const mutation = useMutation({
    mutationFn: () => adminApi.reset(scope),
    onSuccess: (res) => {
      const detail = Object.entries(res.deleted)
        .map(([k, v]) => `${k}:${v}`)
        .join(", ");
      onDone(`✓ ${scope} — ${detail}`);
    },
  });
  const { armed, handleClick } = useDoubleClickConfirm(() => mutation.mutate(), 4000);
  const cls = danger ? "btn danger" : "btn secondary";
  return (
    <button type="button" className={cls} onClick={handleClick} disabled={mutation.isPending}>
      {armed ? t(confirmKey) : t(labelKey)}
    </button>
  );
}

export function Data() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [feedback, setFeedback] = useState<string | null>(null);
  const { data, isLoading } = useQuery<AdminStatsOut>({
    queryKey: ["admin-stats"],
    queryFn: adminApi.stats,
  });

  const onDone = (msg: string) => {
    setFeedback(msg);
    void qc.invalidateQueries({ queryKey: ["admin-stats"] });
  };

  const kpis: Array<[string, string]> = data
    ? [
        [t("data.kpi.projects"), String(data.projects)],
        [t("data.kpi.files"), `${data.files} / ${data.file_versions} ${t("data.kpi.versions")}`],
        [t("data.kpi.anomalies"), String(data.anomalies)],
        [t("data.kpi.runs"), String(data.analysis_runs)],
        [t("data.kpi.chunks"), String(data.document_chunks)],
        [t("data.kpi.chatSessions"), `${data.chat_sessions} / ${data.chat_messages} ${t("data.kpi.messages")}`],
        [t("data.kpi.storage"), fmtBytes(data.storage_bytes)],
        [t("data.kpi.db"), fmtBytes(data.db_bytes)],
      ]
    : [];

  return (
    <>
      <div className="page-header">
        <h1>{t("nav.data")}</h1>
        <p>{t("page.data")}</p>
      </div>

      <div className="card">
        <h2 className="card-title">{t("data.overview")}</h2>
        {isLoading ? (
          <div className="empty-state">{t("common.loading")}</div>
        ) : (
          <div className="kpi-grid">
            {kpis.map(([label, value]) => (
              <div className="kpi" key={label}>
                <div className="label">{label}</div>
                <div className="kpi-value">{value}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">{t("data.resetTitle")}</h2>
        <div className="banner"><RichText text={t("data.resetHint")} /></div>
        <div className="row">
          <ResetButton scope="analyses" labelKey="data.resetAnalyses" confirmKey="data.confirmAnalyses" onDone={onDone} />
          <ResetButton scope="chat" labelKey="data.resetChat" confirmKey="data.confirmChat" onDone={onDone} />
          <ResetButton scope="all" labelKey="data.resetAll" confirmKey="data.confirmAll" danger onDone={onDone} />
          {feedback && <span className="success">{feedback}</span>}
        </div>
        <div className="mt-2 font-mono text-xs text-fg-dim">
          <span>{t("data.scopeAnalyses")}</span> {t("data.scopeAnalysesDetail")}
          <br />
          <span>{t("data.scopeChat")}</span> {t("data.scopeChatDetail")}
          <br />
          <span>{t("data.scopeAll")}</span> {t("data.scopeAllDetail")}
        </div>
      </div>
    </>
  );
}
