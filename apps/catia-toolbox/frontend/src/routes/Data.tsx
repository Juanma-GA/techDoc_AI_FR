import { Spinner } from "@internal/ui";
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
        { key: "diffs", label: t("data.diffs"), value: String(stats.diffs) },
        { key: "conversions", label: t("data.conversions"), value: String(stats.conversions) },
        { key: "colorizations", label: t("data.colorizations"), value: String(stats.colorizations) },
        { key: "nomenclatures", label: t("data.nomenclatures"), value: String(stats.nomenclatures) },
        { key: "smgxmlRuns", label: t("data.smgxmlRuns"), value: String(stats.smgxml_runs) },
        { key: "totalSize", label: t("data.totalSize"), value: formatSize(stats.total_size_bytes) },
      ]
    : [];

  return (
    <div className="form">
      <section className="workflow-section">
        <h2 className="section-title">{t("data.overviewTitle")}</h2>
        {statsQuery.isLoading ? (
          <Spinner aria-label={t("common.loading")} />
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
            <h3 className="section-title">{t("data.statsUnavailable")}</h3>
          </div>
        )}
      </section>

      <DataResetCard title={t("data.resetTitle")} description={t("data.resetBanner")} />
    </div>
  );
}
