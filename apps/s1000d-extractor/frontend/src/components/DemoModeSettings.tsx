import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  DemoModeSelector,
  useDemoMode,
} from "@internal/ui";
import { useTranslation } from "react-i18next";

import { settingsApi } from "../lib/api";

export function DemoModeSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { mode, isReady } = useDemoMode();
  const modeMutation = useMutation({
    mutationFn: (enabled: boolean) => settingsApi.write({ demo_enabled: enabled }),
    onSuccess: async (settings) => {
      await queryClient.cancelQueries();
      queryClient.removeQueries({
        predicate: (query) => query.queryKey[0] !== "settings",
      });
      queryClient.setQueryData(["settings"], settings);
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.demoTitle")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm text-fg-dim">{t("settings.demoHint")}</p>
        <DemoModeSelector
          mode={mode}
          labels={{
            normal: t("settings.normalMode"),
            demo: t("settings.demoMode"),
          }}
          ariaLabel={t("settings.demoTitle")}
          disabled={!isReady || modeMutation.isPending}
          onModeChange={(nextMode) => modeMutation.mutate(nextMode === "demo")}
        />
        {modeMutation.isError ? (
          <p role="alert" className="text-danger">
            {t("settings.demoSaveError")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
