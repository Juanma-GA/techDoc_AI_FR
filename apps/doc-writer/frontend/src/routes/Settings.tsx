import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { DocsManagerCard } from "../components/DocsManagerCard";
import { SettingsModelFields } from "../components/SettingsModelFields";
import { TemplatesManagerCard } from "../components/TemplatesManagerCard";
import { DemoModeSettings } from "./DemoModeSettings";
import {
  ApiClientError,
  settingsApi,
  type ApiTestResultDto,
  type SettingsDto,
  type TestConnectionDto,
} from "../lib/api";

// Page Parametres, pixel-identique au preview (.switch-row / .form / .banner).
export function Settings() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [chatModel, setChatModel] = useState("");
  const [embedModel, setEmbedModel] = useState("");
  const [visionModel, setVisionModel] = useState("");
  const [ocrModel, setOcrModel] = useState("");
  const [transcribeModel, setTranscribeModel] = useState("");
  const [mistralSettingsOpen, setMistralSettingsOpen] = useState(true);
  // Cle/URL DEDIEES a Voxtral (volet discret). Vides = la transcription utilise
  // la cle Mistral principale.
  const [voxtralApiKey, setVoxtralApiKey] = useState("");
  const [voxtralBaseUrl, setVoxtralBaseUrl] = useState("");
  // Modeles fournis par chaque API au test de connexion, sans les deviner.
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [transcriptionModels, setTranscriptionModels] = useState<string[]>([]);
  // Detail du dernier test PAR API appelee (Mistral principale + Voxtral dediee).
  const [apiResults, setApiResults] = useState<ApiTestResultDto[]>([]);
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
    setVisionModel(d.vision_model);
    setOcrModel(d.ocr_model);
    setTranscribeModel(d.transcribe_model);
    setVoxtralBaseUrl(d.voxtral_base_url);
  }, [settingsQuery.data]);

  useEffect(() => {
    if (settingsQuery.data) {
      setMistralSettingsOpen(!settingsQuery.data.api_key_set);
    }
  }, [settingsQuery.data?.api_key_set]);

  const saveMutation = useMutation({
    mutationFn: () =>
      settingsApi.write({
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
        chat_model: chatModel,
        embed_model: embedModel,
        vision_model: visionModel,
        ocr_model: ocrModel,
        transcribe_model: transcribeModel || undefined,
        voxtral_api_key: voxtralApiKey || undefined,
        voxtral_base_url: voxtralBaseUrl,
      }),
    onSuccess: () => {
      setApiKey("");
      setVoxtralApiKey("");
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
      setApiResults(r.apis);
      const vx = r.apis.find((a) => a.api === "voxtral");
      const main = r.apis.find((a) => a.api === "mistral");
      setAvailableModels(main?.ok ? main.models : r.models);
      setTranscriptionModels(
        vx?.ok ? vx.models : main?.ok ? main.models : [],
      );
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
  const voxtralKeySet = cfg?.voxtral_api_key_set ?? false;
  const llmEnabled = cfg?.llm_enabled ?? true;

  return (
    <>
      <div className="page-header">
        <h1>{t("settings.title")}</h1>
        <p>{t("settings.subtitle")}</p>
      </div>

      <DemoModeSettings />

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
          <button
            type="button"
            className="btn ghost small"
            aria-expanded={mistralSettingsOpen}
            aria-controls="mistral-settings-fields"
            onClick={() => setMistralSettingsOpen((open) => !open)}
          >
            {mistralSettingsOpen
              ? t("settings.collapseConfiguration")
              : t("settings.expandConfiguration")}
          </button>
        </h2>
        <div id="mistral-settings-fields" hidden={!mistralSettingsOpen}>
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
          <SettingsModelFields
            chatModel={chatModel}
            setChatModel={setChatModel}
            embedModel={embedModel}
            setEmbedModel={setEmbedModel}
            visionModel={visionModel}
            setVisionModel={setVisionModel}
            ocrModel={ocrModel}
            setOcrModel={setOcrModel}
            transcribeModel={transcribeModel}
            setTranscribeModel={setTranscribeModel}
            availableModels={availableModels}
            transcriptionModels={transcriptionModels}
          />
          <details
            style={{
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "8px 12px",
            }}
          >
            <summary
              style={{
                cursor: "pointer",
                fontSize: "0.82rem",
                color: "var(--fg-dim)",
                userSelect: "none",
              }}
            >
              {t("settings.voxtralSummary")}
              {voxtralKeySet ? (
                <span className="badge ok" style={{ marginLeft: 8 }}>
                  {t("settings.voxtralDedicated")}
                </span>
              ) : null}
            </summary>
            <div className="form" style={{ marginTop: 10 }}>
              <small style={{ color: "var(--fg-dim)", fontSize: "0.78rem" }}>
                {t("settings.voxtralHint")}
              </small>
              <label>
                <div className="label">{t("settings.voxtralApiKeyLabel")}</div>
                <input
                  className="input"
                  type="password"
                  autoComplete="off"
                  placeholder={t("settings.apiKeyPlaceholder")}
                  value={voxtralApiKey}
                  onChange={(e) => setVoxtralApiKey(e.target.value)}
                />
                {voxtralKeySet ? (
                  <small style={{ color: "var(--fg-dim)", fontSize: "0.78rem" }}>
                    {t("settings.apiKeyStored")}
                  </small>
                ) : null}
              </label>
              <label>
                <div className="label">{t("settings.voxtralBaseUrlLabel")}</div>
                <input
                  className="input"
                  type="url"
                  placeholder="https://api.mistral.ai"
                  value={voxtralBaseUrl}
                  onChange={(e) => setVoxtralBaseUrl(e.target.value)}
                />
                <small style={{ color: "var(--fg-dim)", fontSize: "0.78rem" }}>
                  {t("settings.voxtralBaseUrlHint")}
                </small>
              </label>
            </div>
          </details>
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
          {apiResults.length > 0 ? (
            <div className="form" style={{ gap: 6 }}>
              <div className="label">{t("settings.apisTestedLabel")}</div>
              {apiResults.map((a) => (
                <div
                  key={a.api}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    fontSize: "0.82rem",
                  }}
                >
                  <span className={a.ok ? "badge ok" : "badge warn"}>
                    {a.api === "voxtral"
                      ? t("settings.apiVoxtral")
                      : t("settings.apiMistral")}
                  </span>
                  <span style={{ color: "var(--fg-dim)" }}>{a.base_url}</span>
                  <span style={{ marginLeft: "auto", color: "var(--fg-dim)" }}>
                    {a.ok
                      ? t("settings.apiModelsCount", { count: a.models.length })
                      : (a.error ?? t("settings.apiFailed"))}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
          {feedback ? (
            <div className={feedback.kind === "ok" ? "success" : "error"}>
              {feedback.text}
            </div>
          ) : null}
        </div>
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
    </>
  );
}
