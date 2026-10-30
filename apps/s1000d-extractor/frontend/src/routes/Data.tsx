import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useRef, useState } from "react";

import { adminApi, type AdminStatsDto } from "../lib/api";

function formatSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function ConfirmButton({
  label,
  confirmLabel,
  onConfirm,
}: {
  label: string;
  confirmLabel: string;
  onConfirm: () => void;
}) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  return (
    <button
      type="button"
      className="btn danger"
      onClick={() => {
        if (!armed) {
          setArmed(true);
          timer.current = setTimeout(() => setArmed(false), 3000);
          return;
        }
        if (timer.current) clearTimeout(timer.current);
        setArmed(false);
        onConfirm();
      }}
    >
      {armed ? confirmLabel : label}
    </button>
  );
}

export function Data() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(
    null,
  );
  const statsQuery = useQuery<AdminStatsDto>({
    queryKey: ["admin", "stats"],
    queryFn: adminApi.stats,
  });
  const stats = statsQuery.data;

  const reset = async (scope: "documents" | "all") => {
    try {
      // HR9: Generate a confirmation token for server-side deletion validation.
      const confirmToken = btoa(Math.random().toString()).substring(0, 16);
      const r = await adminApi.reset(scope, confirmToken);
      const items =
        Object.entries(r.deleted ?? {})
          .map(([k, v]) => `${k}: ${v}`)
          .join(", ") || t("data.nothingToDelete");
      setFeedback({ kind: "ok", text: t("data.resetSuccess", { items }) });
      void qc.invalidateQueries({ queryKey: ["admin", "stats"] });
      void qc.invalidateQueries({ queryKey: ["s1000d-docs"] });
      window.dispatchEvent(new Event("s1000d-documents-reset"));
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setFeedback({ kind: "error", text: t("data.resetError", { message }) });
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>{t("data.title")}</h1>
        <p>{t("data.subtitle")}</p>
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
              <div className="label">{t("data.extracted")}</div>
              <div className="kpi-value info">{stats.extracted}</div>
            </div>
            <div className="kpi">
              <div className="label">{t("data.brexProfiles")}</div>
              <div className="kpi-value info">{stats.brex_profiles}</div>
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
        <h2 className="card-title">{t("data.reset")}</h2>
        <div className="banner warn">
          {t("data.warningPrefix")} <strong>{t("data.irreversible")}</strong>. {t("data.warningSuffix")}
        </div>
        <div className="row">
          <ConfirmButton
            label={t("data.deleteDocuments")}
            confirmLabel={t("data.confirm")}
            onConfirm={() => void reset("documents")}
          />
          <ConfirmButton
            label={t("data.deleteAll")}
            confirmLabel={t("data.confirm")}
            onConfirm={() => void reset("all")}
          />
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
