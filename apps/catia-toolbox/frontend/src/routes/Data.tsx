import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { DataResetCard } from "../components/business/DataResetCard";
import { adminApi, type AdminStatsDto } from "../lib/api";

function formatSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1048576) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / 1048576).toFixed(2)} MB`;
}

export function Data() {
  const { t } = useTranslation();
  const statsQuery = useQuery<AdminStatsDto>({ queryKey: ["admin", "stats"], queryFn: adminApi.stats });

  const stats = statsQuery.data;
  const kpis: { key: string; label: string; value: string }[] = stats
    ? [
        { key: "imports", label: t("data.imports"), value: String(stats.imports) },
        { key: "nodes", label: t("data.nodes"), value: String(stats.nodes) },
        { key: "runs", label: t("data.runs"), value: String(stats.runs) },
        { key: "suggestions", label: t("data.suggestions"), value: String(stats.suggestions) },
        { key: "diffs", label: t("data.diffs"), value: String(stats.diffs) },
        { key: "checks", label: t("data.checks"), value: String(stats.checks) },
        { key: "conversions", label: t("data.conversions"), value: String(stats.conversions) },
        { key: "replacements", label: t("data.replacements"), value: String(stats.replacements) },
        { key: "colorizations", label: t("data.colorizations"), value: String(stats.colorizations) },
        { key: "nomenclatures", label: t("data.nomenclatures"), value: String(stats.nomenclatures) },
        { key: "smgxmlRuns", label: t("data.smgxmlRuns"), value: String(stats.smgxml_runs) },
        { key: "qcChecklists", label: t("data.qcChecklists"), value: String(stats.qc_checklists) },
        { key: "totalSize", label: t("data.totalSize"), value: formatSize(stats.total_size_bytes) },
      ]
    : [];

  return (
    <div className="form">
      <article className="card">
        <h2 className="card-title">{t("data.overviewTitle")}</h2>
        {statsQuery.isLoading ? (
          <span className="spinner" />
        ) : stats ? (
          <div className="kpi-grid">
            {kpis.map((kpi) => (
              <div key={kpi.key} className="kpi">
                <span className="label">{kpi.label}</span>
                <span className="kpi-value">{kpi.value}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <h3 className="card-title">{t("data.statsUnavailable")}</h3>
          </div>
        )}
      </article>

      <DataResetCard title={t("data.resetTitle")} description={t("data.resetBanner")} />
    </div>
  );
}
