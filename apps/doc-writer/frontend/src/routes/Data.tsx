import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  adminApi,
  ApiClientError,
  type AdminResetScope,
  type AdminStatsDto,
} from "../lib/api";

function formatSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

// Bouton a double-clic, sans confirmation native : 1er clic arme, 2e dans les 3 s
// execute. Classes .btn du preview.
function ConfirmButton({
  label,
  confirmLabel,
  variant,
  disabled,
  onConfirm,
}: {
  label: string;
  confirmLabel: string;
  variant: "secondary" | "danger";
  disabled?: boolean;
  onConfirm: () => void;
}) {
  const [armed, setArmed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fire = () => {
    if (!armed) {
      setArmed(true);
      timer.current = setTimeout(() => setArmed(false), 3000);
      return;
    }
    if (timer.current) clearTimeout(timer.current);
    setArmed(false);
    onConfirm();
  };
  return (
    <button
      type="button"
      className={`btn ${armed ? "danger" : variant}`}
      disabled={disabled}
      onClick={fire}
    >
      {armed ? confirmLabel : label}
    </button>
  );
}

// Onglet Donnees, pixel-identique au preview (.card / .kpi-grid / .kpi /
// .banner.warn / .btn).
export function Data() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [feedback, setFeedback] = useState<
    { kind: "ok" | "error"; message: string } | null
  >(null);

  const statsQuery = useQuery<AdminStatsDto, ApiClientError>({
    queryKey: ["admin", "stats"],
    queryFn: adminApi.stats,
  });

  const reset = async (scope: AdminResetScope) => {
    try {
      const res = await adminApi.reset(scope);
      const items = Object.entries(res.deleted ?? {})
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");
      setFeedback({ kind: "ok", message: t("data.resetOk", { items }) });
      void qc.invalidateQueries({ queryKey: ["admin", "stats"] });
      void qc.invalidateQueries({ queryKey: ["documents"] });
      void qc.invalidateQueries({ queryKey: ["sessions"] });
    } catch (e) {
      setFeedback({
        kind: "error",
        message: e instanceof Error ? e.message : String(e),
      });
    }
  };

  const stats = statsQuery.data;

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
        <div className="banner warn">{t("data.resetWarn")}</div>
        <div className="row">
          <ConfirmButton
            label={t("data.resetDocuments")}
            confirmLabel={t("data.confirmAgain")}
            variant="secondary"
            onConfirm={() => reset("documents")}
          />
          <ConfirmButton
            label={t("data.resetSessions")}
            confirmLabel={t("data.confirmAgain")}
            variant="secondary"
            onConfirm={() => reset("sessions")}
          />
          <ConfirmButton
            label={t("data.resetAll")}
            confirmLabel={t("data.confirmAgain")}
            variant="danger"
            onConfirm={() => reset("all")}
          />
        </div>
        {feedback ? (
          <div className={feedback.kind === "ok" ? "success" : "error"}>
            {feedback.message}
          </div>
        ) : null}
      </div>
    </>
  );
}
