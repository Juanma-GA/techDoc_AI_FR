import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Switch } from "@internal/ui";

import { settingsApi, type SettingsDto, type TestConnectionDto } from "../lib/api";
import { DemoModeSettings } from "./DemoModeSettings";

/**
 * Mistral configuration page — same fields/behavior on every POC (STANDARD_POC.md
 * rule #6): LLM on/off switch, API key (write-only), base URL, chat/embed models,
 * Save + Test connection. Personnalise le libelle/description au bootstrap.
 */
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
      setFeedback({ kind: "ok", text: t("settings.mistral.saveSuccess") });
      void qc.invalidateQueries({ queryKey: ["settings"] });
      void qc.invalidateQueries({ queryKey: ["health"] });
    },
    onError: (e: Error) => setFeedback({ kind: "error", text: e.message }),
  });

  const testMutation = useMutation({
    mutationFn: () => settingsApi.test(),
    onSuccess: (r: TestConnectionDto) => {
      setFeedback(
        r.ok
          ? { kind: "ok", text: t("settings.mistral.testSuccess", { models: r.models.join(", ") }) }
          : { kind: "error", text: t("settings.mistral.testError", { message: r.error ?? "" }) },
      );
      void qc.invalidateQueries({ queryKey: ["health"] });
    },
    onError: (e: Error) => setFeedback({ kind: "error", text: e.message }),
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
          <CardTitle>{t("settings.ai.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="label">{t("settings.ai.toggleLabel")}</div>
              <p className="text-sm text-fg-dim">{t("settings.ai.toggleHint")}</p>
            </div>
            <Switch
              checked={llmEnabled}
              onCheckedChange={(v) => llmToggle.mutate(v)}
              disabled={llmToggle.isPending}
              aria-label={t("settings.ai.toggleLabel")}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {t("settings.mistral.title")}
            <Badge variant={apiKeySet ? "success" : "warning"}>
              {apiKeySet ? t("settings.mistral.configured") : t("settings.mistral.notConfigured")}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="label">{t("settings.mistral.apiKeyLabel")}</span>
            <Input
              type="password"
              autoComplete="off"
              placeholder="sk-..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            {apiKeySet && (
              <span className="text-sm text-fg-dim">{t("settings.mistral.apiKeyHint")}</span>
            )}
          </label>
          <label className="flex flex-col gap-1">
            <span className="label">{t("settings.mistral.baseUrlLabel")}</span>
            <Input type="url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </label>
          <div className="flex gap-3">
            <label className="flex flex-1 flex-col gap-1">
              <span className="label">{t("settings.mistral.chatModelLabel")}</span>
              <Input value={chatModel} onChange={(e) => setChatModel(e.target.value)} />
            </label>
            <label className="flex flex-1 flex-col gap-1">
              <span className="label">{t("settings.mistral.embedModelLabel")}</span>
              <Input value={embedModel} onChange={(e) => setEmbedModel(e.target.value)} />
                <span className="text-sm text-fg-dim">
                  {t("settings.mistral.embedModelOptional")}
                </span>
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
              {t("common.save")}
            </Button>
            <Button
              variant="secondary"
              disabled={testMutation.isPending}
              onClick={() => {
                setFeedback(null);
                testMutation.mutate();
              }}
            >
              {t("settings.mistral.test")}
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
