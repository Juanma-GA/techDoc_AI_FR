import { useTranslation } from "react-i18next";

import type { TreeMetrics } from "../../lib/api";

export function MetricsPanel({ metrics }: { metrics: TreeMetrics }) {
  const { t } = useTranslation();
  const naming = metrics.naming ?? {};
  const styles = Object.keys(naming.styles ?? {});
  return (
    <div className="flex flex-col gap-3">
      <div className="kpi-grid">
        <div className="kpi">
          <span className="label">{t("tree.metrics.files")}</span>
          <span className="kpi-value">{metrics.file_count ?? 0}</span>
        </div>
        <div className="kpi">
          <span className="label">{t("tree.metrics.folders")}</span>
          <span className="kpi-value">{metrics.folder_count ?? 0}</span>
        </div>
        <div className="kpi">
          <span className="label">{t("tree.metrics.maxDepth")}</span>
          <span className="kpi-value">{metrics.max_depth ?? 0}</span>
        </div>
        <div className="kpi">
          <span className="label">{t("tree.metrics.maxFanout")}</span>
          <span className="kpi-value">{metrics.max_fanout ?? 0}</span>
        </div>
        <div className="kpi">
          <span className="label">{t("tree.metrics.duplicates")}</span>
          <span className="kpi-value">{metrics.duplicate_basenames_count ?? 0}</span>
        </div>
        <div className="kpi">
          <span className="label">{t("tree.metrics.deepNesting")}</span>
          <span className="kpi-value">{metrics.deep_nesting_count ?? 0}</span>
        </div>
      </div>
      <div className="row" style={{ flexWrap: "wrap" }}>
        <span className="label">{t("tree.metrics.naming")} :</span>
        {naming.inconsistent ? (
          <span className="badge warn">{t("tree.metrics.inconsistent")}</span>
        ) : (
          <span className="badge ok">{t("tree.metrics.consistent")}</span>
        )}
        {styles.length ? <span className="font-mono text-label">{styles.join(", ")}</span> : null}
      </div>
    </div>
  );
}
