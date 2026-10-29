import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  Button, Card, CardContent, CardHeader, CardTitle, DemoModeSelector, useDemoMode,
} from "@internal/ui";

import { useWorkflow } from "../hooks/WorkflowProvider";
import { settingsApi } from "../lib/api";

export function DemoModeSettings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const workflow = useWorkflow();
  const { mode, isReady } = useDemoMode();
  const [demoImporting, setDemoImporting] = useState(false);
  const [demoImportError, setDemoImportError] = useState("");
  const modeMutation = useMutation({
    mutationFn: (enabled: boolean) => settingsApi.write({ demo_enabled: enabled }),
    onSuccess: (settings) => queryClient.setQueryData(["settings"], settings),
  });

  async function importDemoFiles() {
    setDemoImportError("");
    setDemoImporting(true);
    try {
      await workflow.loadDemoFiles();
      navigate("/");
    } catch (error) {
      setDemoImportError(
        error instanceof Error ? error.message : t("settings.demo.importError"),
      );
    } finally {
      setDemoImporting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("settings.demo.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm text-fg-dim">{t("settings.demo.hint")}</p>
        <DemoModeSelector
          mode={mode}
          labels={{ normal: t("settings.demo.normal"), demo: t("settings.demo.demo") }}
          ariaLabel={t("settings.demo.title")}
          disabled={
            !isReady || !workflow.storage.ready || modeMutation.isPending || demoImporting
          }
          onModeChange={(nextMode) => {
            setDemoImportError("");
            modeMutation.mutate(nextMode === "demo", {
              onSuccess: (settings) => {
                if (settings.demo_enabled) void importDemoFiles();
              },
            });
          }}
        />
        {!workflow.storage.ready && !workflow.storage.startupError ? (
          <p role="status" className="text-sm text-fg-dim">
            {t("settings.demo.workspaceLoading")}
          </p>
        ) : null}
        {workflow.storage.startupError ? (
          <div className="space-y-2">
            <p role="alert" className="text-sm text-danger">
              {t("settings.demo.workspaceError")}
            </p>
            <Button
              variant="secondary"
              onClick={workflow.storage.retryStartup}
            >
              {t("settings.demo.retryWorkspace")}
            </Button>
          </div>
        ) : null}
        {demoImporting ? (
          <p role="status" className="text-sm text-fg-dim">
            {t("settings.demo.importing")}
          </p>
        ) : null}
        {demoImportError ? (
          <div className="space-y-2">
            <p role="alert" className="text-sm text-danger">{demoImportError}</p>
            <Button
              variant="secondary"
              disabled={demoImporting}
              onClick={() => void importDemoFiles()}
            >
              {t("settings.demo.retryImport")}
            </Button>
          </div>
        ) : null}
        {modeMutation.isError ? (
          <p role="alert" className="text-danger">
            {t("settings.demo.saveError")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}