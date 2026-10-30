import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CollapsibleSection,
  FormField,
  Input,
  PageHeader,
  Switch,
} from "@internal/ui";

import { settingsApi, type SettingsDto, type TestConnectionDto } from "../lib/api";
import { DemoModeSettings } from "./DemoModeSettings";

/**
 * Mistral configuration page — same fields/behavior on every POC (STANDARD_POC.md
 * rule #6): LLM on/off switch, API key (write-only), base URL, chat/embed models,
 * Save + Test connection. The Mistral block is a CollapsibleSection, collapsed by
 * default once a key is configured; models returned by the connection test are
 * offered as suggestions while free text stays possible.
 */
export function Settings() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const modelsListId = useId();
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [chatModel, setChatModel] = useState("");
  const [embedModel, setEmbedModel] = useState("");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [mistralOpen, setMistralOpen] = useState<boolean | null>(null);
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
      if (r.ok) setAvailableModels(r.models);
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
  const modelsHint = availableModels.length === 0 ? t("settings.mistral.modelsHint") : undefined;

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <PageHeader title={t("settings.title")} description={t("settings.subtitle")} />
      <DemoModeSettings />
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.ai.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="label">{t("settings.ai.toggleLabel")}</div>
              <p className="m-0 text-sm text-fg-dim">{t("settings.ai.toggleHint")}</p>
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

      <CollapsibleSection
        title={t("settings.mistral.title")}
        open={mistralOpen ?? !apiKeySet}
        onOpenChange={setMistralOpen}
        aside={
          <Badge variant={apiKeySet ? "success" : "warning"}>
            {apiKeySet ? t("settings.mistral.configured") : t("settings.mistral.notConfigured")}
          </Badge>
        }
      >
        <div className="flex flex-col gap-4">
          <FormField
            label={t("settings.mistral.apiKeyLabel")}
            hint={apiKeySet ? t("settings.mistral.apiKeyHint") : undefined}
          >
            <Input
              type="password"
              autoComplete="off"
              placeholder="sk-..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </FormField>
          <FormField label={t("settings.mistral.baseUrlLabel")}>
            <Input type="url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label={t("settings.mistral.chatModelLabel")} hint={modelsHint}>
              <Input
                list={modelsListId}
                value={chatModel}
                onChange={(e) => setChatModel(e.target.value)}
              />
            </FormField>
            <FormField
              label={t("settings.mistral.embedModelLabel")}
              hint={t("settings.mistral.embedModelOptional")}
            >
              <Input
                list={modelsListId}
                value={embedModel}
                onChange={(e) => setEmbedModel(e.target.value)}
              />
            </FormField>
          </div>
          <datalist id={modelsListId}>
            {availableModels.map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
          <div className="flex flex-wrap gap-2">
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
          {feedback ? (
            <Alert variant={feedback.kind === "ok" ? "success" : "danger"}>{feedback.text}</Alert>
          ) : null}
        </div>
      </CollapsibleSection>
    </div>
  );
}