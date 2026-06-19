import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { BarList, type BarItem } from "../components/BarList";
import { ProjectSlicer } from "../components/ProjectSlicer";
import { StackedBarChart } from "../components/StackedBarChart";
import { kpisApi, projectsApi } from "../lib/api";
import { useScopeStore } from "../stores/useScopeStore";
import type { KpiOut, ProjectOut } from "../lib/types";

const SEVERITY_COLOR: Record<string, string> = {
  high: "var(--danger)",
  medium: "var(--warning)",
  low: "var(--success)",
};
const STATUS_KEYS: Record<string, string> = {
  open: "redacteur.statusOpen",
  acknowledged: "redacteur.statusAck",
  fixed: "redacteur.statusFixed",
  rejected: "redacteur.statusRejected",
};

function resolutionClass(rate: number): string {
  if (rate >= 70) return "kpi-value ok";
  if (rate >= 40) return "kpi-value warn";
  return "kpi-value err";
}

export function Manager() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const scope = useScopeStore((s) => s.managerScope);
  const setScope = useScopeStore((s) => s.setManagerScope);
  const setRedacteurProjectId = useScopeStore((s) => s.setRedacteurProjectId);

  const projectsQuery = useQuery<ProjectOut[]>({ queryKey: ["projects"], queryFn: projectsApi.list });
  const sortedScope = [...scope].sort();
  const kpisQuery = useQuery<KpiOut>({
    queryKey: ["kpis", sortedScope],
    queryFn: () => kpisApi.scope(scope),
  });

  const k = kpisQuery.data;
  const sevItems: BarItem[] = k
    ? ["high", "medium", "low"]
        .filter((s) => (k.anomalies_by_severity[s] ?? 0) > 0)
        .map((s) => ({ label: t(`redacteur.sev${s === "high" ? "High" : s === "medium" ? "Medium" : "Low"}`), value: k.anomalies_by_severity[s] ?? 0, color: SEVERITY_COLOR[s] }))
    : [];
  const typeItems: BarItem[] = k
    ? Object.entries(k.anomalies_by_type)
        .filter(([, v]) => v > 0)
        .sort((a, b) => b[1] - a[1])
        .map(([type, v]) => ({ label: t(`projects.kpi.type.${type}`), value: v }))
    : [];

  const canGotoProject = scope.length === 1;
  const gotoRedacteur = () => {
    setRedacteurProjectId(scope.length === 1 ? (scope[0] ?? null) : null);
    navigate("/redacteur");
  };

  return (
    <>
      <div className="page-header">
        <h1>{t("nav.manager")}</h1>
        <p>{t("page.manager")}</p>
      </div>

      <div className="card">
        <h2 className="card-title">{t("manager.selectProject")}</h2>
        <div className="label" style={{ marginBottom: 8 }}>{t("common.slicerHint")}</div>
        <ProjectSlicer projects={projectsQuery.data ?? []} value={scope} onChange={setScope} />
      </div>

      {!k ? (
        <div className="card"><div className="empty-state">{t("common.loading")}</div></div>
      ) : (
        <>
          <div className="card">
            <h2 className="card-title">{t("manager.kpis")}</h2>
            <div className="kpi-grid">
              <Kpi label={t("manager.openAnomalies")} value={k.open_anomalies} cls={k.open_anomalies > 0 ? "kpi-value warn" : "kpi-value ok"} />
              <Kpi label={t("manager.resolutionRate")} value={`${Math.round(k.resolution_rate)}%`} cls={resolutionClass(k.resolution_rate)} />
              <Kpi label={t("manager.totalFiles")} value={`${k.files_total} (${k.files_with_anomalies} ${t("manager.withAnomalies")})`} cls="kpi-value info" />
              <Kpi label={t("manager.avgAge")} value={k.avg_age_days.toFixed(1)} />
              <Kpi label={t("manager.avgRes")} value={k.avg_resolution_days.toFixed(1)} />
            </div>
          </div>

          <div className="grid-2">
            <div className="card">
              <h2 className="card-title">{t("manager.byStatus")}</h2>
              <div className="kpi-grid">
                {(["open", "acknowledged", "fixed", "rejected"] as const).map((s) => (
                  <Kpi key={s} label={t(STATUS_KEYS[s] ?? s)} value={k.anomalies_by_status[s] ?? 0} />
                ))}
              </div>
            </div>
            <div className="card">
              <h2 className="card-title">{t("manager.byConfidence")}</h2>
              <div className="kpi-grid">
                <Kpi label={t("manager.confHigh")} value={k.anomalies_by_confidence.elevee ?? 0} cls="kpi-value ok" />
                <Kpi label={t("manager.confMedium")} value={k.anomalies_by_confidence.moyenne ?? 0} cls="kpi-value warn" />
                <Kpi label={t("manager.confLow")} value={k.anomalies_by_confidence.faible ?? 0} cls="kpi-value err" />
              </div>
            </div>
          </div>

          <div className="grid-2">
            <div className="card">
              <h2 className="card-title">{t("manager.bySeverity")}</h2>
              <BarList items={sevItems} />
            </div>
            <div className="card">
              <h2 className="card-title">{t("manager.byType")}</h2>
              <BarList items={typeItems} />
            </div>
          </div>

          <div className="card">
            <h2 className="card-title">{t("manager.topFiles")}</h2>
            {k.top_files.length ? (
              <div className="file-list">
                {k.top_files.map((f) => (
                  <div className="file-row" key={f.filename}>
                    <span className="file-name">{f.filename}</span>
                    <span className="badge danger">{f.count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">—</div>
            )}
            <div className="row" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="btn secondary small"
                disabled={!canGotoProject}
                title={canGotoProject ? undefined : t("manager.gotoProjectHint")}
                onClick={() => canGotoProject && navigate(`/projects/${scope[0]}`)}
              >
                {t("manager.gotoProject")}
              </button>
              <button type="button" className="btn secondary small" onClick={gotoRedacteur}>
                {t("manager.gotoRedacteur")}
              </button>
            </div>
          </div>

          <div className="card">
            <h2 className="card-title">{t("manager.overTime")}</h2>
            <StackedBarChart runs={k.anomalies_over_time} />
          </div>
        </>
      )}
    </>
  );
}

function Kpi({ label, value, cls = "kpi-value" }: { label: string; value: string | number; cls?: string }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className={cls}>{value}</div>
    </div>
  );
}
