import { useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "../components/PageHeader";
import {
  useAiPrompt,
  useMistralSettings,
  useTestMistralConnection,
  useToggleLlm,
  useUpdateAiPrompt,
  useUpdateMistralSettings,
} from "../hooks/useMistralSettings";
import { useStandards } from "../hooks/useStandards";
import { useFiltersStore } from "../stores/filtersStore";

import { Rules } from "./Rules";
import { Standards } from "./Standards";

export function Settings() {
  const { t } = useTranslation();
  const targetUnits = useFiltersStore((s) => s.targetUnits);
  const toggleTargetUnit = useFiltersStore((s) => s.toggleTargetUnit);
  const activeStandardVersionIds = useFiltersStore((s) => s.activeStandardVersionIds);
  const toggleActiveStandardVersion = useFiltersStore((s) => s.toggleActiveStandardVersion);
  const clearActiveStandards = useFiltersStore((s) => s.clearActiveStandards);

  const standards = useStandards();
  // Libelles des versions actives, pour le resume « Actives · CODE v1 · … ».
  const activeLabels = (standards.data ?? []).flatMap((s) =>
    s.versions
      .filter((v) => activeStandardVersionIds.includes(v.id))
      .map((v) => `${s.code} ${v.label}`),
  );

  const mistral = useMistralSettings();
  const updateMistral = useUpdateMistralSettings();
  const testMistral = useTestMistralConnection();
  const toggleLlm = useToggleLlm();
  const aiPrompt = useAiPrompt();
  const updateAiPrompt = useUpdateAiPrompt();

  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const [baseUrlDraft, setBaseUrlDraft] = useState("");
  const [modelDraft, setModelDraft] = useState("");
  const [visionModelDraft, setVisionModelDraft] = useState("");
  const [promptDraft, setPromptDraft] = useState<string | null>(null);

  const effectivePrompt = promptDraft ?? aiPrompt.data?.prompt ?? "";

  const submitMistral = (): void => {
    updateMistral.mutate(
      {
        api_key: apiKeyDraft || undefined,
        base_url: baseUrlDraft || undefined,
        chat_model: modelDraft || undefined,
        vision_model: visionModelDraft || undefined,
      },
      {
        onSuccess: () => {
          setApiKeyDraft("");
          setBaseUrlDraft("");
          setModelDraft("");
          setVisionModelDraft("");
        },
      },
    );
  };

  return (
    <div>
      <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />

      <section className="form">
        {/* 0. Configuration LLM (Mistral) — EN TETE, pliee par defaut. */}
        <Collapsible title={t("settings.llmSection")}>
          <Card
            title={t("settings.mistral.title")}
            description={t("settings.mistral.description")}
          >
            {mistral.isLoading ? (
              <p className="hint">{t("common.loading")}</p>
            ) : (
              <div className="form">
                <div className="switch-row">
                  <div>
                    <div>{t("settings.mistral.llmEnabled")}</div>
                    <div className="label">{t("settings.mistral.llmEnabledHint")}</div>
                  </div>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!mistral.data?.llm_enabled}
                      onChange={(e) => toggleLlm.mutate(e.target.checked)}
                    />
                    <span className="track" />
                  </label>
                </div>

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
                <Field label={t("settings.mistral.visionModel")}>
                  <input
                    placeholder={mistral.data?.vision_model ?? "pixtral-12b-2409"}
                    value={visionModelDraft}
                    onChange={(e) => setVisionModelDraft(e.target.value)}
                    className="input mono"
                  />
                </Field>
                <label className="checkbox" style={{ gap: 8 }}>
                  <input
                    type="checkbox"
                    checked={!!mistral.data?.vision_enabled}
                    onChange={(e) => updateMistral.mutate({ vision_enabled: e.target.checked })}
                  />
                  <span>{t("settings.mistral.visionEnabled")}</span>
                </label>

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
        </Collapsible>

        {/* 1. Normes cibles actives (multi-select pills, parite preview) :
            chaque version selectionnee est fusionnee a l'analyse et appliquee
            a chaque upload. Choix persistant (filtersStore). */}
        <Card
          title={t("settings.activeStandards.title")}
          description={t("settings.activeStandards.hint")}
        >
          {standards.isLoading ? (
            <p className="hint">{t("common.loading")}</p>
          ) : (standards.data ?? []).length === 0 ? (
            <p className="empty-state">{t("common.empty")}</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {(standards.data ?? []).map((std) => {
                const stdActive = std.versions.some((v) =>
                  activeStandardVersionIds.includes(v.id),
                );
                return (
                <div
                  key={std.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    flexWrap: "wrap",
                    padding: "8px 10px",
                    // Surbrillance de la norme quand au moins une version est
                    // active (en plus des pills bleues).
                    background: stdActive ? "var(--card-hover)" : "var(--bg-2)",
                    border: `1px solid ${stdActive ? "var(--brand-light)" : "var(--border)"}`,
                    borderRadius: 8,
                  }}
                >
                  <span
                    style={{
                      fontFamily: '"JetBrains Mono", monospace',
                      color: "var(--fg)",
                      minWidth: 120,
                    }}
                  >
                    {std.code}
                  </span>
                  <span
                    className="label"
                    style={{ color: "var(--fg-dim)", flex: 1, minWidth: 0 }}
                  >
                    {std.label}
                  </span>
                  {std.versions.map((v) => {
                    const on = activeStandardVersionIds.includes(v.id);
                    return (
                      <button
                        key={v.id}
                        type="button"
                        aria-pressed={on}
                        onClick={() => toggleActiveStandardVersion(v.id)}
                        className={on ? "slicer-pill active" : "slicer-pill"}
                      >
                        {v.label}
                        {v.builtin ? "" : ` (${t("standards.custom")})`}
                      </button>
                    );
                  })}
                </div>
                );
              })}
            </div>
          )}
          <div className="row" style={{ marginTop: 10 }}>
            <span className="label" style={{ color: "var(--fg-dim)" }}>
              {activeLabels.length > 0
                ? t("settings.activeStandards.activeNow", { list: activeLabels.join(" · ") })
                : t("settings.activeStandards.none")}
            </span>
            <button
              type="button"
              className="btn ghost small"
              style={{ marginLeft: "auto" }}
              onClick={clearActiveStandards}
              disabled={activeStandardVersionIds.length === 0}
            >
              {t("settings.activeStandards.clear")}
            </button>
          </div>
        </Card>

        {/* 2. Administration des normes (catalogue + versions) — pliee par defaut. */}
        <Collapsible title={t("settings.standardsAdmin")}>
          <Standards />
        </Collapsible>

        {/* 5. Regles custom (linter user-defined) — imbriquee dans Parametres */}
        <Rules />

        {/* 6. Systemes d'unites cibles (multi : metric et/ou imperial). */}
        <Card title={t("settings.targetUnit.title")} description={t("settings.targetUnit.multiHint")}>
          <div className="slicer">
            {(["metric", "imperial"] as const).map((opt) => {
              const on = targetUnits.includes(opt);
              return (
                <button
                  key={opt}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleTargetUnit(opt)}
                  className={on ? "slicer-pill active" : "slicer-pill"}
                >
                  {t(`settings.targetUnit.${opt}`)}
                </button>
              );
            })}
            <span className="label" style={{ alignSelf: "center", marginLeft: 6 }}>
              {targetUnits.length === 1
                ? ""
                : `${t("settings.targetUnit.auto")} (${t("settings.targetUnit.bothHint")})`}
            </span>
          </div>
        </Card>
      </section>
    </div>
  );
}

function Collapsible({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <details className="collapsible" open={defaultOpen} style={{ marginBottom: 4 }}>
      <summary
        className="card-title"
        style={{ cursor: "pointer", listStyle: "none", padding: "6px 2px", userSelect: "none" }}
      >
        ▸ {title}
      </summary>
      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 16 }}>
        {children}
      </div>
    </details>
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
