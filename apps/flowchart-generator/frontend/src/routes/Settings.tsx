import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Switch } from "@internal/ui";

import { errorText, settingsApi, type SettingsDto, type TestConnectionDto } from "../lib/api";
import { DemoModeSettings } from "./DemoModeSettings";

// Configuration Mistral standard (STANDARD_POC.md regle #6) : interrupteur LLM, cle, URL, modeles.
export function Settings() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [chatModel, setChatModel] = useState("");
  const [embedModel, setEmbedModel] = useState("");
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const settingsQuery = useQuery<SettingsDto>({ queryKey: ["settings"], queryFn: settingsApi.read });

  useEffect(() => {
    const d = settingsQuery.data;
    if (!d) return;
    setBaseUrl(d.base_url);
    setChatModel(d.chat_model);
    setEmbedModel(d.embed_model);
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      settingsApi.write({
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
        chat_model: chatModel,
        embed_model: embedModel,
      }),
    onSuccess: () => {
      setApiKey("");
      setFeedback({ kind: "ok", text: t("settings.saved") });
      void qc.invalidateQueries({ queryKey: ["settings"] });
      void qc.invalidateQueries({ queryKey: ["health"] });
    },
    onError: (e: unknown) => setFeedback({ kind: "error", text: errorText(e) }),
  });

  const testMutation = useMutation({
    mutationFn: () => settingsApi.test(),
    onSuccess: (r: TestConnectionDto) => {
      setFeedback(
        r.ok
          ? { kind: "ok", text: t("settings.testOk", { count: r.models.length }) }
          : { kind: "error", text: t("settings.testFail", { error: r.error ?? "" }) },
      );
      void qc.invalidateQueries({ queryKey: ["health"] });
    },
    onError: (e: unknown) => setFeedback({ kind: "error", text: errorText(e) }),
  });

  const llmToggle = useMutation({
    mutationFn: (enabled: boolean) => settingsApi.write({ llm_enabled: enabled }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["settings"] });
      void qc.invalidateQueries({ queryKey: ["health"] });
    },
  });

  const cfg = settingsQuery.data;
  const apiKeySet = cfg?.api_key_set ?? false;
  const llmEnabled = cfg?.llm_enabled ?? true;

  return (
    <div className="flex max-w-xl flex-col gap-4">
      <DemoModeSettings />
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.aiTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between gap-3">
            <div>
              <div>{t("settings.llmEnabled")}</div>
              <p className="text-fg-dim">
                {t("settings.llmHelp")}
              </p>
            </div>
            <Switch
              checked={llmEnabled}
              onCheckedChange={(v) => llmToggle.mutate(v)}
              disabled={llmToggle.isPending}
              aria-label={t("settings.llmEnabled")}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {t("settings.mistralTitle")}
            <Badge variant={apiKeySet ? "success" : "warning"}>
              {apiKeySet ? t("settings.configured") : t("settings.notConfigured")}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span>{t("settings.apiKey")}</span>
            <Input
              type="password"
              autoComplete="off"
              placeholder="sk-..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            {apiKeySet && (
              <span className="text-fg-dim">
                {t("settings.apiKeyKept")}
              </span>
            )}
          </label>
          <label className="flex flex-col gap-1">
            <span>{t("settings.baseUrl")}</span>
            <Input type="url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </label>
          <div className="flex gap-3">
            <label className="flex flex-1 flex-col gap-1">
              <span>{t("settings.chatModel")}</span>
              <Input value={chatModel} onChange={(e) => setChatModel(e.target.value)} />
            </label>
            <label className="flex flex-1 flex-col gap-1">
              <span>{t("settings.embedModel")}</span>
              <Input value={embedModel} onChange={(e) => setEmbedModel(e.target.value)} />
            </label>
          </div>
          <div className="flex gap-2">
            <Button
              variant="primary"
              disabled={saveMutation.isPending}
              onClick={() => {
                setFeedback(null);
                saveMutation.mutate();
              }}
            >
              {t("settings.save")}
            </Button>
            <Button
              variant="secondary"
              disabled={testMutation.isPending}
              onClick={() => {
                setFeedback(null);
                testMutation.mutate();
              }}
            >
              {t("settings.test")}
            </Button>
          </div>
          {feedback && (
            <div className={feedback.kind === "ok" ? "text-success" : "text-danger"}>
              {feedback.text}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
