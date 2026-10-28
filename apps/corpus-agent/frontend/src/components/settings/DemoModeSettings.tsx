import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, DemoModeSelector, useDemoMode } from "@internal/ui";
import { useTranslation } from "react-i18next";

import { demoSettingsApi } from "../../lib/api";

export function DemoModeSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { mode, isReady } = useDemoMode();
  const modeMutation = useMutation({
    mutationFn: (enabled: boolean) => demoSettingsApi.write({ demo_enabled: enabled }),
    onSuccess: (settings) => {
      queryClient.setQueryData(["app-settings"], settings);
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["kpis"] });
    },
  });

  return (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle>{t("settings.demo.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm text-fg-dim">{t("settings.demo.hint")}</p>
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
