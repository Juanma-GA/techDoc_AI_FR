import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { DocsManagerCard } from "../components/DocsManagerCard";
import { PromptsCard } from "../components/PromptsCard";
import { TemplatesManagerCard } from "../components/TemplatesManagerCard";
import {
  ApiClientError,
  settingsApi,
  type SettingsDto,
  type TestConnectionDto,
} from "../lib/api";

// Page Parametres, pixel-identique au preview (.switch-row / .form / .banner).
// Mistral = cle / base_url / chat / embed (vision/ocr non exposes, parite preview).
export function Settings() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [chatModel, setChatModel] = useState("");
  const [embedModel, setEmbedModel] = useState("");
  const [transcribeModel, setTranscribeModel] = useState("");
  // Modeles disponibles decouverts au test de connexion (/v1/models), pour
  // proposer le bon id de transcription sans le deviner.
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [feedback, setFeedback] = useState<
    { kind: "ok" | "error"; text: string } | null
  >(null);

  const settingsQuery = useQuery<SettingsDto, ApiClientError>({
    queryKey: ["settings"],
    queryFn: settingsApi.read,
  });

  // Initialise le formulaire quand la config arrive.
  useEffect(() => {
    const d = settingsQuery.data;
    if (!d) return;
    setBaseUrl(d.base_url);
    setChatModel(d.chat_model);
    setEmbedModel(d.embed_model);
    setTranscribeModel(d.transcribe_model);
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      settingsApi.write({
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
        chat_model: chatModel,
        embed_model: embedModel,
        transcribe_model: transcribeModel || undefined,
      }),
    onSuccess: () => {
      setApiKey("");
      setFeedback({ kind: "ok", text: t("settings.saved") });
      void qc.invalidateQueries({ queryKey: ["settings"] });
      // Rafraichit le badge LLM du sidebar (la cle change l'etat /health).
      void qc.invalidateQueries({ queryKey: ["health"] });
    },
    onError: (e: ApiClientError) => setFeedback({ kind: "error", text: e.message }),
  });

  const testMutation = useMutation({
    mutationFn: () => settingsApi.test(),
    onSuccess: (r: TestConnectionDto) => {
      if (r.ok) setAvailableModels(r.models);
      setFeedback(
        r.ok
          ? { kind: "ok", text: t("settings.testOk", { count: r.models.length }) }
          : { kind: "error", text: t("settings.testFailed", { error: r.error ?? "" }) },
      );
      void qc.invalidateQueries({ queryKey: ["health"] });
    },
    onError: (e: ApiClientError) => setFeedback({ kind: "error", text: e.message }),
  });

  const llmToggleMutation = useMutation({
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
    <>
      <div className="page-header">
        <h1>{t("settings.title")}</h1>
        <p>{t("settings.subtitle")}</p>
      </div>

      <div className="card">
        <h2 className="card-title">{t("settings.llmSectionTitle")}</h2>
        <div className="switch-row">
          <div>
            <div className="label">{t("settings.llmEnabledLabel")}</div>
            <small style={{ color: "var(--fg-dim)", fontSize: "0.78rem" }}>
              {t("settings.llmEnabledHint")}
            </small>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={llmEnabled}
              disabled={llmToggleMutation.isPending}
              onChange={(e) => llmToggleMutation.mutate(e.target.checked)}
            />
            <span className="track" />
          </label>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">
          <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
            Mistral
            {apiKeySet ? (
              <span className="badge ok">CONFIGURED</span>
            ) : (
              <span className="badge warn">NOT CONFIGURED</span>
            )}
          </span>
        </h2>
        <div className="form">
          <label>
            <div className="label">{t("settings.apiKeyLabel")}</div>
            <input
              className="input"
              type="password"
              autoComplete="off"
              placeholder={t("settings.apiKeyPlaceholder")}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            {apiKeySet ? (
              <small style={{ color: "var(--fg-dim)", fontSize: "0.78rem" }}>
                {t("settings.apiKeyStored")}
              </small>
            ) : null}
          </label>
          <label>
            <div className="label">{t("settings.baseUrlLabel")}</div>
            <input
              className="input"
              type="url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </label>
          <div className="row">
            <label className="grow">
              <div className="label">{t("settings.chatModelLabel")}</div>
              <input
                className="input"
                type="text"
                value={chatModel}
                onChange={(e) => setChatModel(e.target.value)}
              />
            </label>
            <label className="grow">
              <div className="label">{t("settings.embedModelLabel")}</div>
              <input
                className="input"
                type="text"
                value={embedModel}
                onChange={(e) => setEmbedModel(e.target.value)}
              />
            </label>
          </div>
          <label>
            <div className="label">{t("settings.transcribeModelLabel")}</div>
            {availableModels.length > 0 && (
              <select
                className="input"
                value={availableModels.includes(transcribeModel) ? transcribeModel : ""}
                onChange={(e) => setTranscribeModel(e.target.value)}
                style={{ marginBottom: 6 }}
              >
                <option value="">{t("settings.transcribeModelPick")}</option>
                {[...availableModels]
                  .sort((a, b) => Number(b.includes("voxtral")) - Number(a.includes("voxtral")))
                  .map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
              </select>
            )}
            <input
              className="input"
              type="text"
              placeholder="voxtral-..."
              value={transcribeModel}
              onChange={(e) => setTranscribeModel(e.target.value)}
            />
            <small style={{ color: "var(--fg-dim)", fontSize: "0.78rem" }}>
              {availableModels.length > 0
                ? t("settings.transcribeModelHintTested", { count: availableModels.length })
                : t("settings.transcribeModelHint")}
            </small>
          </label>
          <div className="row">
            <button
              type="button"
              className="btn primary"
              disabled={saveMutation.isPending}
              onClick={() => {
                setFeedback(null);
                saveMutation.mutate();
              }}
            >
              {t("settings.save")}
            </button>
            <button
              type="button"
              className="btn secondary"
              disabled={testMutation.isPending}
              onClick={() => {
                setFeedback(null);
                testMutation.mutate();
              }}
            >
              {t("settings.test")}
            </button>
          </div>
          {feedback ? (
            <div className={feedback.kind === "ok" ? "success" : "error"}>
              {feedback.text}
            </div>
          ) : null}
        </div>
      </div>

      <div className="banner">
        <strong>{t("settings.refsHintTitle")}</strong> {t("settings.refsHintBody")}
      </div>

      <TemplatesManagerCard />
      <DocsManagerCard
        kind="style"
        title={t("settings.styleDocsTitle")}
        hint={t("settings.styleDocsHint")}
        accept=".pptx,.docx,.pdf,.txt,.md"
      />
      <PromptsCard />
    </>
  );
}
