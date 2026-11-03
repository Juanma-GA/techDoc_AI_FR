import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useState } from "react";

import {
  Alert,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  EmptyState,
  KpiCard,
  PageHeader,
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  Toaster,
} from "@internal/ui";
import { adminApi, type AdminStatsDto } from "../lib/api";
import { createConfirmToken } from "../lib/confirmToken";
import { formatApiError } from "../lib/migrationUtils";
import { ConfirmButton } from "../components/ConfirmButton";

function formatSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

export function Data() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [feedback, setFeedback] = useState<{
    kind: "success" | "danger";
    text: string;
  } | null>(null);
  const statsQuery = useQuery<AdminStatsDto>({
    queryKey: ["admin", "stats"],
    queryFn: adminApi.stats,
  });
  const stats = statsQuery.data;

  const reset = async (scope: "documents" | "all") => {
    try {
      const confirmToken = createConfirmToken();
      const r = await adminApi.reset(scope, confirmToken);
      const items =
        Object.entries(r.deleted ?? {})
          .map(([k, v]) => `${k}: ${v}`)
          .join(", ") || t("data.nothingToDelete");
      setFeedback({ kind: "success", text: t("data.resetSuccess", { items }) });
      void qc.invalidateQueries({ queryKey: ["admin", "stats"] });
      void qc.invalidateQueries({ queryKey: ["s1000d-docs"] });
      window.dispatchEvent(new Event("s1000d-documents-reset"));
    } catch (e) {
      const message = formatApiError(t, e);
      setFeedback({ kind: "danger", text: t("data.resetError", { message }) });
    }
  };

  return (
    <ToastProvider duration={5000}>
      <div className="space-y-4">
        <PageHeader title={t("data.title")} description={t("data.subtitle")} />

        <Card>
          <CardHeader><CardTitle>{t("data.overview")}</CardTitle></CardHeader>
          <CardContent>
            {stats ? (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <KpiCard label={t("data.documents")} value={stats.documents} />
                <KpiCard label={t("data.extracted")} value={stats.extracted} />
                <KpiCard label={t("data.brexProfiles")} value={stats.brex_profiles} />
                <KpiCard label={t("data.totalSize")} value={formatSize(stats.total_size_bytes)} />
              </div>
            ) : (
              <EmptyState title={t("data.statsUnavailable")} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>{t("data.reset")}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <Alert variant="warning">
              {t("data.warningPrefix")} <strong>{t("data.irreversible")}</strong>.{" "}
              {t("data.warningSuffix")}
            </Alert>
            <div className="flex flex-wrap gap-3">
              <ConfirmButton
                label={t("data.deleteDocuments")}
                onConfirm={() => void reset("documents")}
              />
              <ConfirmButton
                label={t("data.deleteAll")}
                onConfirm={() => void reset("all")}
              />
            </div>
          </CardContent>
        </Card>
      </div>
      {feedback ? (
        <Toast
          open
          variant={feedback.kind}
          onOpenChange={(open) => {
            if (!open) setFeedback(null);
          }}
        >
          <div>
            <ToastTitle>
              {t(feedback.kind === "success" ? "data.resetSuccessTitle" : "data.resetErrorTitle")}
            </ToastTitle>
            <ToastDescription>{feedback.text}</ToastDescription>
          </div>
          <ToastClose aria-label={t("common.close")} />
        </Toast>
      ) : null}
      <Toaster />
    </ToastProvider>
  );
}
