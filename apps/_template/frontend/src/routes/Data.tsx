import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  KpiCard,
  PageHeader,
  Skeleton,
} from "@internal/ui";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { adminApi } from "../lib/api";

export function Data() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [armed, setArmed] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const statsQuery = useQuery({
    queryKey: ["admin", "stats"],
    queryFn: adminApi.stats,
  });

  const resetMutation = useMutation({
    mutationFn: adminApi.resetAll,
    onSuccess: async (result) => {
      const deleted = Object.values(result.deleted).reduce((sum, count) => sum + count, 0);
      setFeedback(t("data.resetDone", { count: deleted }));
      await queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
    },
    onError: (error: Error) => setFeedback(error.message),
  });

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );

  const resetAll = () => {
    if (resetMutation.isPending) return;
    if (!armed) {
      setFeedback(null);
      setArmed(true);
      timerRef.current = setTimeout(() => setArmed(false), 3000);
      return;
    }
    if (timerRef.current) clearTimeout(timerRef.current);
    setArmed(false);
    resetMutation.mutate();
  };

  const stats = statsQuery.data;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("data.title")} description={t("data.subtitle")} />

      <Card>
        <CardHeader>
          <CardTitle>{t("data.overview")}</CardTitle>
        </CardHeader>
        <CardContent>
          {statsQuery.isPending ? (
            <div role="status" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <span className="sr-only">{t("common.loading")}</span>
              {Array.from({ length: 5 }, (_, index) => (
                <Skeleton key={index} className="h-[68px] rounded-lg" />
              ))}
            </div>
          ) : statsQuery.isError ? (
            <Alert variant="danger">{statsQuery.error.message}</Alert>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <KpiCard label={t("data.documents")} value={stats?.documents ?? 0} />
              <KpiCard label={t("data.chunks")} value={stats?.chunks ?? 0} />
              <KpiCard label={t("data.sessions")} value={stats?.sessions ?? 0} />
              <KpiCard label={t("data.messages")} value={stats?.messages ?? 0} />
              <KpiCard label={t("data.storage")} value={formatBytes(stats?.total_size_bytes ?? 0)} />
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("data.resetTitle")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <p className="m-0 mr-auto text-fg-dim">{t("data.resetHint")}</p>
          <Button
            variant="danger"
            size="sm"
            disabled={resetMutation.isPending}
            onClick={resetAll}
          >
            {resetMutation.isPending
              ? t("common.loading")
              : armed
                ? t("common.confirm")
                : t("data.resetButton")}
          </Button>
          {feedback ? <span role="status" className="text-sm text-fg-dim">{feedback}</span> : null}
        </CardContent>
      </Card>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = units[0];
  for (let index = 1; value >= 1024 && index < units.length; index += 1) {
    value /= 1024;
    unit = units[index];
  }
  return `${value.toFixed(1)} ${unit}`;
}