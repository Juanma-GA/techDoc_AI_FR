import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  LlmSettingsPanel,
  PageHeader,
  type LlmSettingsDraft,
  type LlmSettingsFeedback,
  type LlmSettingsValue,
} from "@internal/ui";

import { settingsApi, type SettingsDto, type TestConnectionDto } from "../lib/api";
import { DemoModeSettings } from "./DemoModeSettings";

/**
 * Settings page of the `llm` profile (STANDARD_POC.md rules #6 and #14).
 * The Mistral block is the shared `LlmSettingsPanel` (collapsed once a key is
 * configured, LLM switch always visible, provider models offered after the test).
 * Add app-specific LLM options as children of the panel.
 */
export function Settings() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<LlmSettingsFeedback | null>(null);

  const settingsQuery = useQuery<SettingsDto>({ queryKey: ["settings"], queryFn: settingsApi.read });

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["settings"] });
    void qc.invalidateQueries({ queryKey: ["health"] });
  };

  const saveMutation = useMutation({
    mutationFn: (draft: LlmSettingsDraft) =>
      settingsApi.write({
        api_key: draft.apiKey,
        base_url: draft.baseUrl || undefined,
        chat_model: draft.models.chat ?? "",
        embed_model: draft.models.embed ?? "",
      }),
    onSuccess: () => {
      setFeedback({ kind: "success", message: t("settings.mistral.saveSuccess") });
      refresh();
    },
    onError: (e: Error) => setFeedback({ kind: "danger", message: e.message }),
  });

  const testMutation = useMutation({
    mutationFn: () => settingsApi.test(),
    onSuccess: (r: TestConnectionDto) => {
      if (r.ok) setAvailableModels(r.models);
      setFeedback(
        r.ok
          ? { kind: "success", message: t("settings.mistral.testSuccess", { models: r.models.join(", ") }) }
          : { kind: "danger", message: t("settings.mistral.testError", { message: r.error ?? "" }) },
      );
      void qc.invalidateQueries({ queryKey: ["health"] });
    },
    onError: (e: Error) => setFeedback({ kind: "danger", message: e.message }),
  });

  const toggleMutation = useMutation({
    mutationFn: (enabled: boolean) => settingsApi.write({ llm_enabled: enabled }),
    onSuccess: refresh,
  });

  const cfg = settingsQuery.data;
  const value: LlmSettingsValue | undefined = cfg
    ? {
        llmEnabled: cfg.llm_enabled,
        apiKeySet: cfg.api_key_set,
        baseUrl: cfg.base_url,
        models: { chat: cfg.chat_model, embed: cfg.embed_model },
      }
    : undefined;

  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <PageHeader title={t("settings.title")} description={t("settings.subtitle")} />
      <DemoModeSettings />
      <LlmSettingsPanel
        value={value}
        availableModels={availableModels}
        onSave={(draft) => {
          setFeedback(null);
          return saveMutation.mutateAsync(draft);
        }}
        onTest={() => {
          setFeedback(null);
          testMutation.mutate();
        }}
        onToggleEnabled={(enabled) => toggleMutation.mutate(enabled)}
        saving={saveMutation.isPending}
        testing={testMutation.isPending}
        toggling={toggleMutation.isPending}
        feedback={feedback}
        labels={{
          title: t("settings.mistral.title"),
          configured: t("settings.mistral.configured"),
          notConfigured: t("settings.mistral.notConfigured"),
          disabled: t("settings.mistral.disabled"),
          enabled: t("settings.ai.toggleLabel"),
          enabledHint: t("settings.ai.toggleHint"),
          apiKey: t("settings.mistral.apiKeyLabel"),
          apiKeyKeep: t("settings.mistral.apiKeyHint"),
          baseUrl: t("settings.mistral.baseUrlLabel"),
          models: {
            chat: t("settings.mistral.chatModelLabel"),
            embed: t("settings.mistral.embedModelLabel"),
          },
          optionalModel: t("settings.mistral.embedModelOptional"),
          modelsHint: t("settings.mistral.modelsHint"),
          save: t("common.save"),
          test: t("settings.mistral.test"),
          loading: t("common.loading"),
        }}
      />
    </div>
  );
}
