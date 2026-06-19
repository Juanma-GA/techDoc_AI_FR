import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { adminApi, type AdminStatsDto } from "../lib/api";

function formatSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

export function Data() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(
    null,
  );
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const statsQuery = useQuery<AdminStatsDto>({
    queryKey: ["admin", "stats"],
    queryFn: adminApi.stats,
  });
  const stats = statsQuery.data;

  const resetAll = async () => {
    if (!armed) {
      setArmed(true);
      timer.current = setTimeout(() => setArmed(false), 3000);
      return;
    }
    if (timer.current) clearTimeout(timer.current);
    setArmed(false);
    try {
      const r = await adminApi.reset("all");
      const items =
        Object.entries(r.deleted ?? {})
          .map(([k, v]) => `${k}: ${v}`)
          .join(", ") || t("data.resetEmpty");
      setFeedback({ kind: "ok", text: t("data.resetOkPrefix") + items });
      void qc.invalidateQueries({ queryKey: ["admin", "stats"] });
    } catch (e) {
      setFeedback({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>{t("routes.data.title")}</h1>
        <p>{t("routes.data.sub")}</p>
      </div>

      <div className="card">
        <h2 className="card-title">{t("data.overview")}</h2>
        {stats ? (
          <div className="kpi-grid">
            <div className="kpi">
              <div className="label">{t("data.documents")}</div>
              <div className="kpi-value info">{stats.documents}</div>
            </div>
            <div className="kpi">
              <div className="label">{t("data.chunks")}</div>
              <div className="kpi-value info">{stats.chunks}</div>
            </div>
            <div className="kpi">
              <div className="label">{t("data.sessions")}</div>
              <div className="kpi-value info">{stats.sessions}</div>
            </div>
            <div className="kpi">
              <div className="label">{t("data.messages")}</div>
              <div className="kpi-value info">{stats.messages}</div>
            </div>
            <div className="kpi">
              <div className="label">{t("data.totalSize")}</div>
              <div className="kpi-value">{formatSize(stats.total_size_bytes)}</div>
            </div>
          </div>
        ) : (
          <div className="empty-state">{t("data.statsUnavailable")}</div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">{t("data.resetTitle")}</h2>
        <div className="banner warn">{t("data.resetWarning")}</div>
        <div className="row">
          <button
            type="button"
            className="btn danger"
            onClick={() => void resetAll()}
          >
            {armed ? t("data.confirmAgain") : t("data.resetAll")}
          </button>
        </div>
        {feedback ? (
          <div className={feedback.kind === "ok" ? "success" : "error"}>
            {feedback.text}
          </div>
        ) : null}
      </div>
    </>
  );
}
