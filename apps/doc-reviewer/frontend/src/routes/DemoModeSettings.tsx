import { useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  DemoModeSelector,
  useDemoMode,
} from "@internal/ui";
import { useTranslation } from "react-i18next";

import { useUpdateMistralSettings } from "../hooks/useMistralSettings";

export function DemoModeSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { mode, isReady } = useDemoMode();
  const updateSettings = useUpdateMistralSettings();

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.demo.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm text-fg-dim">{t("settings.demo.hint")}</p>
        <DemoModeSelector
          mode={mode}
          labels={{
            normal: t("settings.demo.normal"),
            demo: t("settings.demo.demo"),
          }}
          ariaLabel={t("settings.demo.title")}
          disabled={!isReady || updateSettings.isPending}
          onModeChange={(nextMode) =>
            updateSettings.mutate(
              { demo_enabled: nextMode === "demo" },
              {
                onSuccess: (settings) => {
                  queryClient.setQueryData(["settings", "mistral"], settings);
                  void queryClient.invalidateQueries({ queryKey: ["client-config"] });
                  void queryClient.invalidateQueries({ queryKey: ["client-rules"] });
                  void queryClient.invalidateQueries({ queryKey: ["standards"] });
                },
              },
            )
          }
        />
        {updateSettings.isError ? (
          <p role="alert" className="text-danger">
            {t("settings.demo.saveError")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
