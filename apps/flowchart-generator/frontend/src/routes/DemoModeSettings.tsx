import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle, DemoModeSelector, useDemoMode } from "@internal/ui";

import { settingsApi } from "../lib/api";

export function DemoModeSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { mode, isReady } = useDemoMode();
  const modeMutation = useMutation({
    mutationFn: (enabled: boolean) => settingsApi.write({ demo_enabled: enabled }),
    onSuccess: (settings) => queryClient.setQueryData(["settings"], settings),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.demo.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-fg-dim">{t("settings.demo.hint")}</p>
        <DemoModeSelector
          mode={mode}
          labels={{ normal: t("settings.demo.normal"), demo: t("settings.demo.demo") }}
          ariaLabel={t("settings.demo.title")}
          disabled={!isReady || modeMutation.isPending}
          onModeChange={(nextMode) => modeMutation.mutate(nextMode === "demo")}
        />
        {modeMutation.isError ? (
          <p role="alert" className="text-danger">
            {t("settings.demo.saveError")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}