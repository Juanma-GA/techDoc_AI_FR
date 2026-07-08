import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Spinner, Switch } from "@internal/ui";

import { TemplatesCard } from "../components/TemplatesCard";
import { settingsApi, type SettingsDto, type TestConnectionDto } from "../lib/api";

export function Settings() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery<SettingsDto>({ queryKey: ["settings"], queryFn: settingsApi.read });

  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [chatModel, setChatModel] = useState("");
  const [testResult, setTestResult] = useState<TestConnectionDto | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (data) {
      setBaseUrl(data.base_url);
      setChatModel(data.chat_model);
    }
  }, [data]);

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["settings"] });
    void qc.invalidateQueries({ queryKey: ["health"] });
  };

  const save = async () => {
    setBusy(true);
    try {
      const body: Record<string, unknown> = { base_url: baseUrl, chat_model: chatModel };
      if (apiKey) body.api_key = apiKey;
      await settingsApi.save(body);
      setApiKey("");
      setTestResult(null);
      refresh();
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    setBusy(true);
    try {
      setTestResult(await settingsApi.test());
      refresh();
    } finally {
      setBusy(false);
    }
  };

  const toggleLlm = async (enabled: boolean) => {
    await settingsApi.save({ llm_enabled: enabled });
    refresh();
  };

  if (isLoading || !data) return <Spinner />;

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between rounded-sm border border-md bg-card p-3">
            <span className="text-sm text-fg">{t("settings.llmEnabled")}</span>
            <Switch
              checked={data.llm_enabled}
              onCheckedChange={(v) => void toggleLlm(v)}
              aria-label={t("settings.llmEnabled")}
            />
          </div>

          <label className="flex flex-col gap-1">
            <span className="label">{t("settings.apiKey")}</span>
            <Input
              type="password"
              value={apiKey}
              placeholder={data.api_key_set ? "••••••••" : t("settings.apiKeyPlaceholder")}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="label">{t("settings.baseUrl")}</span>
            <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </label>

          <label className="flex flex-col gap-1">
            <span className="label">{t("settings.chatModel")}</span>
            <Input value={chatModel} onChange={(e) => setChatModel(e.target.value)} />
          </label>

          <div className="flex items-center gap-2">
            <Button size="sm" onClick={() => void save()} disabled={busy}>
              {t("common.save")}
            </Button>
            <Button variant="secondary" size="sm" onClick={() => void test()} disabled={busy}>
              {t("settings.test")}
            </Button>
          </div>

          {testResult && (
            <p className={`text-sm ${testResult.ok ? "text-success" : "text-danger"}`}>
              {testResult.ok
                ? t("settings.testOk", { count: testResult.models.length })
                : `${t("settings.testFailed")}: ${testResult.error ?? ""}`}
            </p>
          )}
        </CardContent>
      </Card>

      <TemplatesCard />
    </div>
  );
}
