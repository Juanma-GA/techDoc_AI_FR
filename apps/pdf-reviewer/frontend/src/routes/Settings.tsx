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
    <div>
      <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />

      <section className="form">
        <Card title={t("settings.language")}>
          <select
            value={i18n.language.startsWith("en") ? "en" : "fr"}
            onChange={(e) => {
              void i18n.changeLanguage(e.target.value);
            }}
            className="input"
          >
            <option value="fr">Français</option>
            <option value="en">English</option>
          </select>
        </Card>

        <Card title={t("settings.targetUnit.title")}>
          <div className="row">
            {(["metric", "imperial", "auto"] as const).map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setTargetUnit(opt)}
                className={["btn small", targetUnit === opt ? "primary" : "secondary"].join(
                  " ",
                )}
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
          <div className="banner row" style={{ justifyContent: "space-between" }}>
            <div className="row">
              <BookOpen size={16} aria-hidden="true" />
              <span className="label">
                {t("settings.standardsSummary.builtin", { count: builtinCount })}
                {" · "}
                {t("settings.standardsSummary.custom", { count: customCount })}
              </span>
            </div>
            <Link to="/standards" className="btn primary small">
              {t("settings.standardsSummary.manage")}
              <ArrowRight size={14} aria-hidden="true" />
            </Link>
          </div>
          <ul className="grid-2" style={{ marginTop: 12 }}>
            {STRUCTURAL_KINDS.map((kind) => (
              <li key={kind} className="label">
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
            <p className="hint">{t("common.loading")}</p>
          ) : (
            <div className="form">
              <p className="hint" style={{ fontFamily: '"JetBrains Mono", monospace' }}>
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
                  className="input mono"
                />
              </Field>
              <Field label={t("settings.mistral.baseUrl")}>
                <input
                  placeholder={mistral.data?.base_url ?? "https://api.mistral.ai"}
                  value={baseUrlDraft}
                  onChange={(e) => setBaseUrlDraft(e.target.value)}
                  className="input mono"
                />
              </Field>
              <Field label={t("settings.mistral.chatModel")}>
                <input
                  placeholder={mistral.data?.chat_model ?? "mistral-small-latest"}
                  value={modelDraft}
                  onChange={(e) => setModelDraft(e.target.value)}
                  className="input mono"
                />
              </Field>

              <div className="row">
                <button
                  type="button"
                  className="btn primary"
                  onClick={submitMistral}
                  disabled={updateMistral.isPending}
                >
                  {t("common.save")}
                </button>
                <button
                  type="button"
                  className="btn secondary"
                  onClick={() => testMistral.mutate()}
                  disabled={testMistral.isPending}
                >
                  {t("settings.mistral.test")}
                </button>
                {testMistral.data ? (
                  <span className={testMistral.data.ok ? "hint" : "error"}>
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
            <p className="hint">{t("common.loading")}</p>
          ) : (
            <div className="form">
              <textarea
                rows={6}
                value={effectivePrompt}
                onChange={(e) => setPromptDraft(e.target.value)}
                placeholder={t("settings.aiPrompt.placeholder")}
                className="input mono"
              />
              <div className="row">
                <button
                  type="button"
                  className="btn primary"
                  onClick={() => {
                    if (promptDraft === null) return;
                    updateAiPrompt.mutate(promptDraft, {
                      onSuccess: () => setPromptDraft(null),
                    });
                  }}
                  disabled={promptDraft === null || updateAiPrompt.isPending}
                >
                  {t("common.save")}
                </button>
                {promptDraft !== null ? (
                  <button
                    type="button"
                    className="btn secondary"
                    onClick={() => setPromptDraft(null)}
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
    <article className="card">
      <h2 className="card-title">{title}</h2>
      {description ? <p className="card-sub">{description}</p> : null}
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
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}
