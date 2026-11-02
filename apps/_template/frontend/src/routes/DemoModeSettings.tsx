import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { DemoModeSettingsCard, useDemoMode } from "@internal/ui";

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
    <DemoModeSettingsCard
      mode={mode}
      labels={{
        title: t("settings.demo.title"),
        hint: t("settings.demo.hint"),
        normal: t("settings.demo.normal"),
        demo: t("settings.demo.demo"),
        saveError: t("settings.demo.saveError"),
      }}
      disabled={!isReady || modeMutation.isPending}
      error={modeMutation.isError}
      onModeChange={(nextMode) => modeMutation.mutate(nextMode === "demo")}
    />
  );
}