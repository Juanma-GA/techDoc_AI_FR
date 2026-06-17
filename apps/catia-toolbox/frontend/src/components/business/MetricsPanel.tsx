import { Badge, KpiCard } from "@internal/ui";
import { useTranslation } from "react-i18next";

import type { TreeMetrics } from "../../lib/api";

export function MetricsPanel({ metrics }: { metrics: TreeMetrics }) {
  const { t } = useTranslation();
  const naming = metrics.naming ?? {};
  const styles = Object.keys(naming.styles ?? {});
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <KpiCard label={t("tree.metrics.files")} value={metrics.file_count ?? 0} />
        <KpiCard label={t("tree.metrics.folders")} value={metrics.folder_count ?? 0} />
        <KpiCard label={t("tree.metrics.maxDepth")} value={metrics.max_depth ?? 0} />
        <KpiCard label={t("tree.metrics.maxFanout")} value={metrics.max_fanout ?? 0} />
        <KpiCard label={t("tree.metrics.duplicates")} value={metrics.duplicate_basenames_count ?? 0} />
        <KpiCard label={t("tree.metrics.deepNesting")} value={metrics.deep_nesting_count ?? 0} />
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm text-fg-dim">
        <span>{t("tree.metrics.naming")} :</span>
        {naming.inconsistent ? (
          <Badge variant="warning">{t("tree.metrics.inconsistent")}</Badge>
        ) : (
          <Badge variant="success">{t("tree.metrics.consistent")}</Badge>
        )}
        {styles.length ? <span className="font-mono text-label">{styles.join(", ")}</span> : null}
      </div>
    </div>
  );
}
