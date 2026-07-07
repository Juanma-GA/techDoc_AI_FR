import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle, KpiCard, Spinner } from "@internal/ui";

import { ConfirmButton } from "../components/ConfirmButton";
import { adminApi, type AdminStatsDto } from "../lib/api";
import { useCatiStore } from "../stores/useCatiStore";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function Data() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const setSelectedDocId = useCatiStore((s) => s.setSelectedDocId);
  const { data, isLoading } = useQuery<AdminStatsDto>({ queryKey: ["admin-stats"], queryFn: adminApi.stats });

  const afterReset = () => {
    setSelectedDocId(null);
    void qc.invalidateQueries({ queryKey: ["admin-stats"] });
    void qc.invalidateQueries({ queryKey: ["documents"] });
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("data.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading || !data ? (
            <Spinner />
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <KpiCard label={t("data.documents")} value={data.documents} />
              <KpiCard label={t("data.items")} value={data.items} />
              <KpiCard label={t("data.size")} value={formatBytes(data.total_size_bytes)} />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("data.resetTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <ConfirmButton
            variant="secondary"
            label={t("data.resetDocuments")}
            confirmLabel={t("common.confirm")}
            onConfirm={() => adminApi.resetDocuments().then(afterReset)}
          />
          <ConfirmButton
            label={t("data.resetAll")}
            confirmLabel={t("common.confirm")}
            onConfirm={() => adminApi.resetAll().then(afterReset)}
          />
          <p className="w-full text-sm text-fg-dim">{t("data.resetHint")}</p>
        </CardContent>
      </Card>
    </div>
  );
}
