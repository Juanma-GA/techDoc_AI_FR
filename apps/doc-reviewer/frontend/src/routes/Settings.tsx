import { useQueryClient } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageHeader } from "../components/PageHeader";
import {
  useMistralSettings,
  useReliability,
  useTestMistralConnection,
  useToggleLlm,
  useUpdateMistralSettings,
  useUpdateReliability,
} from "../hooks/useMistralSettings";
import { api } from "../lib/api";
import { useStandards } from "../hooks/useStandards";
import { useFiltersStore } from "../stores/filtersStore";
import type { ResetAllResult, WipeSuggestionsResult } from "../types/domain";

import { Rules } from "./Rules";
import { Standards } from "./Standards";

export function Settings() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
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

  const toggleStandard = (versionIds: string[]): void => {
    if (versionIds.length === 0) return;
    const allActive = versionIds.every((id) => activeStandardVersionIds.includes(id));
    for (const versionId of versionIds) {
      const isActive = activeStandardVersionIds.includes(versionId);
      if (allActive ? isActive : !isActive) toggleActiveStandardVersion(versionId);
    }
  };

  const mistral = useMistralSettings();
  const updateMistral = useUpdateMistralSettings();
  const testMistral = useTestMistralConnection();
  const toggleLlm = useToggleLlm();
  const reliability = useReliability();
  const updateReliability = useUpdateReliability();
  const setChecklistActive = useFiltersStore((s) => s.setChecklistActive);

  const [apiKeyDraft, setApiKeyDraft] = useState("");
  const [baseUrlDraft, setBaseUrlDraft] = useState("");
  const [modelDraft, setModelDraft] = useState("");
  const [visionModelDraft, setVisionModelDraft] = useState("");
  const [resetDialog, setResetDialog] = useState<"sugs" | "all" | null>(null);
  const [resetFeedback, setResetFeedback] = useState<string | null>(null);
  const [resetBusy, setResetBusy] = useState(false);

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

  // Choisir un modele dans la liste renvoyee par le test de connexion
  // l'enregistre immediatement (pas de saisie libre -> pas de risque de
  // faute de frappe), pour eviter la question "dois-je encore enregistrer ?".
  const pickModel = (id: string): void => {
    updateMistral.mutate({ chat_model: id });
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

                <div className="switch-row">
                  <div>
                    <div>{t("settings.mistral.checklistAiScan")}</div>
                    <div className="label">{t("settings.mistral.checklistAiScanHint")}</div>
                  </div>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={!!mistral.data?.checklist_ai_scan}
                      onChange={(e) =>
                        updateMistral.mutate({ checklist_ai_scan: e.target.checked })
                      }
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
                    placeholder="https://api.mistral.ai"
                    value={baseUrlDraft || mistral.data?.base_url || ""}
                    onChange={(e) => setBaseUrlDraft(e.target.value)}
                    className="input mono"
                  />
                </Field>
                <Field label={t("settings.mistral.chatModel")}>
                  <input
                    placeholder="mistral-small-latest"
                    value={modelDraft || mistral.data?.chat_model || ""}
                    onChange={(e) => setModelDraft(e.target.value)}
                    className="input mono"
                  />
                </Field>
                <Field label={t("settings.mistral.visionModel")}>
                  <input
                    placeholder="mistral-medium-3-5"
                    value={visionModelDraft || mistral.data?.vision_model || ""}
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

                {testMistral.data?.ok && testMistral.data.models.length > 0 ? (
                  <div className="form" style={{ gap: 6 }}>
                    <span className="label">{t("settings.mistral.modelsFound")}</span>
                    <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                      {testMistral.data.models.map((id) => (
                        <button
                          key={id}
                          type="button"
                          className="btn ghost small mono"
                          title={t("settings.mistral.useThisModel")}
                          disabled={updateMistral.isPending}
                          onClick={() => pickModel(id)}
                        >
                          {id}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </Card>

          <Card
            title={t("settings.reliability.title")}
            description={t("settings.reliability.description")}
          >
            {reliability.isLoading || !reliability.data ? (
              <p className="hint">{t("common.loading")}</p>
            ) : (
              <div className="form">
                <div className="switch-row">
                  <div>
                    <div>{t("settings.reliability.verifyEnabled")}</div>
                    <div className="label">{t("settings.reliability.verifyEnabledHint")}</div>
                  </div>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={reliability.data.verify_enabled}
                      onChange={(e) =>
                        updateReliability.mutate({ verify_enabled: e.target.checked })
                      }
                    />
                    <span className="track" />
                  </label>
                </div>

                <Field label={t("settings.reliability.passes")}>
                  <input
                    type="number"
                    min={1}
                    max={5}
                    value={reliability.data.verify_passes}
                    disabled={!reliability.data.verify_enabled}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      if (Number.isFinite(v)) updateReliability.mutate({ verify_passes: v });
                    }}
                    className="input mono"
                  />
                </Field>
                <p className="hint">{t("settings.reliability.passesHint")}</p>

                <Field label={t("settings.reliability.maxCalls")}>
                  <input
                    type="number"
                    min={0}
                    max={5000}
                    step={50}
                    value={reliability.data.max_calls}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      if (Number.isFinite(v)) updateReliability.mutate({ max_calls: v });
                    }}
                    className="input mono"
                  />
                </Field>
                <p className="hint">{t("settings.reliability.maxCallsHint")}</p>

                <div className="switch-row">
                  <div>
                    <div>{t("settings.reliability.feedbackEnabled")}</div>
                    <div className="label">{t("settings.reliability.feedbackEnabledHint")}</div>
                  </div>
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={reliability.data.feedback_enabled}
                      onChange={(e) =>
                        updateReliability.mutate({ feedback_enabled: e.target.checked })
                      }
                    />
                    <span className="track" />
                  </label>
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
                const versionIds = std.versions.map((v) => v.id);
                const stdActive = std.versions.some((v) =>
                  activeStandardVersionIds.includes(v.id),
                );
                const allVersionsActive =
                  versionIds.length > 0 && versionIds.every((id) => activeStandardVersionIds.includes(id));
                return (
                <div
                  key={std.id}
                  className="standard-option"
                  role={versionIds.length > 0 ? "button" : undefined}
                  tabIndex={versionIds.length > 0 ? 0 : undefined}
                  aria-pressed={versionIds.length > 0 ? allVersionsActive : undefined}
                  aria-label={`${std.code} ${std.label}`}
                  onClick={() => toggleStandard(versionIds)}
                  onKeyDown={(event) => {
                    if (event.target !== event.currentTarget) return;
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      toggleStandard(versionIds);
                    }
                  }}
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
                    cursor: versionIds.length > 0 ? "pointer" : "default",
                  }}
                >
                  <span
                    className="standard-option-code"
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
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleActiveStandardVersion(v.id);
                        }}
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

        <Card title={t("data.reset")}>
          <div className="banner warn">{t("data.resetWarn")}</div>
          <div className="row">
            <button
              type="button"
              disabled={resetBusy}
              onClick={() => setResetDialog("sugs")}
              className="btn secondary"
            >
              {t("data.resetSugs")}
            </button>
            <button
              type="button"
              disabled={resetBusy}
              onClick={() => setResetDialog("all")}
              className="btn danger"
            >
              {t("data.resetAll")}
            </button>
            {resetFeedback ? <span className="hint">{resetFeedback}</span> : null}
          </div>
        </Card>
      </section>

      <ConfirmDialog
        open={resetDialog === "sugs"}
        onOpenChange={(open) => setResetDialog(open ? "sugs" : null)}
        title={t("data.resetSugs")}
        description={t("data.confirmSugs")}
        confirmLabel={t("data.resetSugs")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => {
          setResetBusy(true);
          setResetFeedback(null);
          void api
            .post<WipeSuggestionsResult>("/admin/wipe-suggestions")
            .then((result) => {
              setResetFeedback(t("data.wipedSugs", { count: result.deleted }));
              return queryClient.invalidateQueries({ queryKey: ["suggestions"] });
            })
            .catch((error: unknown) => {
              setResetFeedback(error instanceof Error ? error.message : String(error));
            })
            .finally(() => setResetBusy(false));
        }}
      />
      <ConfirmDialog
        open={resetDialog === "all"}
        onOpenChange={(open) => setResetDialog(open ? "all" : null)}
        title={t("data.resetAll")}
        description={t("data.confirmAll")}
        confirmLabel={t("data.resetAll")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => {
          setResetBusy(true);
          setResetFeedback(null);
          void api
            .post<ResetAllResult>("/admin/reset")
            .then((result) => {
              clearActiveStandards();
              setChecklistActive(false);
              const folders = result.storage_folders_cleaned + result.orphan_folders_cleaned;
              setResetFeedback(
                t("data.resetDone", {
                  docs: result.documents_deleted,
                  rules: result.rules_deleted + result.checklist_rules_deleted,
                  folders,
                }),
              );
              return queryClient.invalidateQueries();
            })
            .catch((error: unknown) => {
              setResetFeedback(error instanceof Error ? error.message : String(error));
            })
            .finally(() => setResetBusy(false));
        }}
      />
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
        className="collapsible-summary card-title"
        style={{ cursor: "pointer", listStyle: "none", userSelect: "none" }}
      >
        <ChevronRight size={16} aria-hidden="true" />
        <span>{title}</span>
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
