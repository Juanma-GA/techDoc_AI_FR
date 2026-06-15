import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { PageHeader } from "../components/PageHeader";
import { resources, type KpiOut } from "../lib/api";

function KpiCard({ label, value, unit }: { label: string; value: string | number; unit?: string }) {
  return (
    <div className="rounded-lg border bg-card p-5 shadow-card">
      <p className="text-xs font-medium uppercase tracking-wider text-fg-dim">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-fg">
        {value}
        {unit && <span className="ml-1 text-base font-normal text-fg-dim">{unit}</span>}
      </p>
    </div>
  );
}

function KpiGrid({ kpis }: { kpis: KpiOut }) {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-5">
      <KpiCard label={t("dashboard.openAnomalies")} value={kpis.open_anomalies} />
      <KpiCard label={t("dashboard.filesTotal")} value={kpis.files_total} />
      <KpiCard label={t("dashboard.filesWithAnomalies")} value={kpis.files_with_anomalies} />
      <KpiCard label={t("dashboard.resolutionRate")} value={kpis.resolution_rate} unit="%" />
      <KpiCard label={t("dashboard.avgAgeDays")} value={kpis.avg_age_days} unit="j" />
    </div>
  );
}

export function Dashboard() {
  const { t } = useTranslation();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["kpis"],
    queryFn: resources.kpis.global,
  });

  return (
    <div className="px-8 py-6">
      <PageHeader
        title={t("routes.dashboard.title")}
        subtitle={t("routes.dashboard.subtitle")}
      />
      {isLoading && (
        <p className="text-fg-dim">{t("common.loading")}</p>
      )}
      {isError && (
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-card p-4 text-sm text-red-400">
          <span>{t("errors.generic")}</span>
          <button
            type="button"
            onClick={() => void refetch()}
            className="underline hover:no-underline"
          >
            {t("common.retry")}
          </button>
        </div>
      )}
      {data && data.files_total === 0 && (
        <p className="text-sm text-fg-dim">{t("dashboard.noData")}</p>
      )}
      {data && data.files_total > 0 && <KpiGrid kpis={data} />}
    </div>
  );
}
