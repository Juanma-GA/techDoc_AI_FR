import { ArrowRight, BookOpen } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { StandardPicker } from "../components/upload/StandardPicker";
import {
  useAiPrompt,
  useMistralSettings,
  useTestMistralConnection,
  useUpdateAiPrompt,
  useUpdateMistralSettings,
} from "../hooks/useMistralSettings";
import { useStandards } from "../hooks/useStandards";
import { useFiltersStore } from "../stores/filtersStore";

const STRUCTURAL_KINDS = [
  "field_required",
  "section_required",
  "field_consistency",
  "step_pattern",
  "enum_value",
] as const;

export function Settings() {
  const { t, i18n } = useTranslation();
  const targetUnit = useFiltersStore((s) => s.targetUnit);
  const setTargetUnit = useFiltersStore((s) => s.setTargetUnit);
  const lastStandardId = useFiltersStore((s) => s.lastStandardId);
  const lastStandardVersionId = useFiltersStore((s) => s.lastStandardVersionId);
  const setLastStandard = useFiltersStore((s) => s.setLastStandard);

  const standards = useStandards();
  const standardCount = standards.data?.length ?? 0;
  const builtinCount = (standards.data ?? []).filter((s) => s.builtin).length;
  const customCount = standardCount - builtinCount;

  const mistral = useMistralSettings();
  const updateMistral = useUpdateMistralSettings();
  const testMistral = useTestMistralConnection();
  const aiPrompt = useAiPrompt();
  const updateAiPrompt = useUpdateAiPrompt();

  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const [baseUrlDraft, setBaseUrlDraft] = useState("");
  const [modelDraft, setModelDraft] = useState("");
  const [promptDraft, setPromptDraft] = useState<string | null>(null);

  const effectivePrompt = promptDraft ?? aiPrompt.data?.prompt ?? "";

  const submitMistral = (): void => {
    updateMistral.mutate(
      {
        api_key: apiKeyDraft || undefined,
        base_url: baseUrlDraft || undefined,
        chat_model: modelDraft || undefined,
      },
      {
        onSuccess: () => {
          setApiKeyDraft("");
          setBaseUrlDraft("");
          setModelDraft("");
        },
      },
    );
  };

  return (
    <div className="flex flex-col">
      <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />

      <section className="grid max-w-3xl gap-8 p-6">
        <Card title={t("settings.language")}>
          <select
            value={i18n.language.startsWith("en") ? "en" : "fr"}
            onChange={(e) => {
              void i18n.changeLanguage(e.target.value);
            }}
            className="w-full max-w-xs rounded-sm border bg-bg-2 px-2 py-1 text-fg"
          >
            <option value="fr">Français</option>
            <option value="en">English</option>
          </select>
        </Card>

        <Card title={t("settings.targetUnit.title")}>
          <div className="flex gap-2">
            {(["metric", "imperial", "auto"] as const).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setTargetUnit(opt)}
                className={[
                  "rounded-sm border px-3 py-1.5 text-sm",
                  targetUnit === opt
                    ? "bg-brand text-fg"
                    : "text-fg-dim hover:bg-card-hover hover:text-fg",
                ].join(" ")}
              >
                {t(`settings.targetUnit.${opt}`)}
              </button>
            ))}
          </div>
        </Card>

        <Card
          title={t("settings.defaultStandard.title")}
          description={t("settings.defaultStandard.description")}
        >
          <StandardPicker
            standardId={lastStandardId}
            versionId={lastStandardVersionId}
            onChange={setLastStandard}
          />
        </Card>

        <Card
          title={t("settings.standardsSummary.title")}
          description={t("settings.standardsSummary.description")}
        >
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border bg-bg-2 px-4 py-3">
            <div className="flex items-center gap-2 text-fg">
              <BookOpen size={16} aria-hidden="true" />
              <span className="font-mono">
                {t("settings.standardsSummary.builtin", { count: builtinCount })}
                {" · "}
                {t("settings.standardsSummary.custom", { count: customCount })}
              </span>
            </div>
            <Link
              to="/standards"
              className="inline-flex items-center gap-1 rounded-sm bg-brand px-3 py-1 text-sm text-fg hover:bg-brand-blue-light"
            >
              {t("settings.standardsSummary.manage")}
              <ArrowRight size={14} aria-hidden="true" />
            </Link>
          </div>
          <ul className="mt-3 grid grid-cols-2 gap-1 text-xs text-fg-dim md:grid-cols-3">
            {STRUCTURAL_KINDS.map((kind) => (
              <li key={kind} className="font-mono">
                · {t(`rules.kind.${kind}`)}
              </li>
            ))}
          </ul>
        </Card>

        <Card
          title={t("settings.mistral.title")}
          description={t("settings.mistral.description")}
        >
          {mistral.isLoading ? (
            <p className="text-fg-dim">{t("common.loading")}</p>
          ) : (
            <div className="flex flex-col gap-3">
              <p className="font-mono text-xs text-fg-dim">
                {mistral.data?.api_key_set
                  ? t("settings.mistral.keySet", { preview: mistral.data.api_key_preview })
                  : t("settings.mistral.keyMissing")}
                {" · "}
                {mistral.data?.base_url}
                {" · "}
                {mistral.data?.chat_model}
              </p>

              <Field label={t("settings.mistral.apiKey")}>
                <input
                  type="password"
                  autoComplete="off"
                  placeholder={t("settings.mistral.apiKeyPlaceholder")}
                  value={apiKeyDraft}
                  onChange={(e) => setApiKeyDraft(e.target.value)}
                  className="w-full rounded-sm border bg-bg-2 px-2 py-1 font-mono text-fg"
                />
              </Field>
              <Field label={t("settings.mistral.baseUrl")}>
                <input
                  placeholder={mistral.data?.base_url ?? "https://api.mistral.ai"}
                  value={baseUrlDraft}
                  onChange={(e) => setBaseUrlDraft(e.target.value)}
                  className="w-full rounded-sm border bg-bg-2 px-2 py-1 font-mono text-fg"
                />
              </Field>
              <Field label={t("settings.mistral.chatModel")}>
                <input
                  placeholder={mistral.data?.chat_model ?? "mistral-small-latest"}
                  value={modelDraft}
                  onChange={(e) => setModelDraft(e.target.value)}
                  className="w-full rounded-sm border bg-bg-2 px-2 py-1 font-mono text-fg"
                />
              </Field>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={submitMistral}
                  disabled={updateMistral.isPending}
                  className="rounded-sm bg-brand px-3 py-1.5 text-sm text-fg hover:bg-brand-blue-light disabled:opacity-50"
                >
                  {t("common.save")}
                </button>
                <button
                  type="button"
                  onClick={() => testMistral.mutate()}
                  disabled={testMistral.isPending}
                  className="rounded-sm border px-3 py-1.5 text-sm text-fg-dim hover:bg-card-hover hover:text-fg disabled:opacity-50"
                >
                  {t("settings.mistral.test")}
                </button>
                {testMistral.data ? (
                  <span
                    className={[
                      "text-xs",
                      testMistral.data.ok ? "text-fg" : "text-danger",
                    ].join(" ")}
                  >
                    {testMistral.data.message}
                  </span>
                ) : null}
              </div>
            </div>
          )}
        </Card>

        <Card
          title={t("settings.aiPrompt.title")}
          description={t("settings.aiPrompt.description")}
        >
          {aiPrompt.isLoading ? (
            <p className="text-fg-dim">{t("common.loading")}</p>
          ) : (
            <div className="flex flex-col gap-2">
              <textarea
                rows={6}
                value={effectivePrompt}
                onChange={(e) => setPromptDraft(e.target.value)}
                placeholder={t("settings.aiPrompt.placeholder")}
                className="w-full rounded-sm border bg-bg-2 px-2 py-2 font-mono text-fg"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    if (promptDraft === null) return;
                    updateAiPrompt.mutate(promptDraft, {
                      onSuccess: () => setPromptDraft(null),
                    });
                  }}
                  disabled={promptDraft === null || updateAiPrompt.isPending}
                  className="rounded-sm bg-brand px-3 py-1.5 text-sm text-fg hover:bg-brand-blue-light disabled:opacity-50"
                >
                  {t("common.save")}
                </button>
                {promptDraft !== null ? (
                  <button
                    type="button"
                    onClick={() => setPromptDraft(null)}
                    className="rounded-sm border px-3 py-1.5 text-sm text-fg-dim hover:bg-card-hover"
                  >
                    {t("common.cancel")}
                  </button>
                ) : null}
              </div>
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}

function Card({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <article className="flex flex-col gap-3 rounded-lg border bg-card p-5">
      <header>
        <h2 className="font-display text-fg">{title}</h2>
        {description ? <p className="text-xs text-fg-dim">{description}</p> : null}
      </header>
      {children}
    </article>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <label className="flex flex-col gap-1 text-xs text-fg-dim">
      <span className="label">{label}</span>
      {children}
    </label>
  );
}
