import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { settingsApi, type SettingsDto, type TestConnectionDto } from "../lib/api";

export function Settings() {
  const qc = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [chatModel, setChatModel] = useState("");
  const [embedModel, setEmbedModel] = useState("");
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; text: string } | null>(
    null,
  );

  const settingsQuery = useQuery<SettingsDto>({
    queryKey: ["settings"],
    queryFn: settingsApi.read,
  });

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
      setFeedback({ kind: "ok", text: "Paramètres enregistrés." });
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
          ? { kind: "ok", text: `Connexion OK (${r.models.length} modèles disponibles).` }
          : { kind: "error", text: `Échec : ${r.error ?? ""}` },
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
    <>
      <div className="page-header">
        <h1>Paramètres</h1>
        <p>Clé API Mistral et modèles utilisés.</p>
      </div>

      <div className="card">
        <h2 className="card-title">Intelligence artificielle</h2>
        <div className="switch-row">
          <div>
            <div className="label">LLM activé</div>
            <small style={{ color: "var(--fg-dim)", fontSize: "0.78rem" }}>
              Désactiver coupe les tâches confiées à l'IA (OCR scans, classification,
              découpage). La clé Mistral est conservée.
            </small>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              checked={llmEnabled}
              disabled={llmToggle.isPending}
              onChange={(e) => llmToggle.mutate(e.target.checked)}
            />
            <span className="track" />
          </label>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">
          <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
            Configuration Mistral
            {apiKeySet ? (
              <span className="badge ok">CONFIGURED</span>
            ) : (
              <span className="badge warn">NOT CONFIGURED</span>
            )}
          </span>
        </h2>
        <div className="form">
          <label>
            <div className="label">Clé API Mistral</div>
            <input
              className="input"
              type="password"
              autoComplete="off"
              placeholder="sk-..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            {apiKeySet ? (
              <small style={{ color: "var(--fg-dim)", fontSize: "0.78rem" }}>
                Une clé est déjà enregistrée (laisser vide pour la conserver).
              </small>
            ) : null}
          </label>
          <label>
            <div className="label">Base URL</div>
            <input
              className="input"
              type="url"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </label>
          <div className="row">
            <label className="grow">
              <div className="label">Modèle chat</div>
              <input
                className="input"
                value={chatModel}
                onChange={(e) => setChatModel(e.target.value)}
              />
            </label>
            <label className="grow">
              <div className="label">Modèle embeddings</div>
              <input
                className="input"
                value={embedModel}
                onChange={(e) => setEmbedModel(e.target.value)}
              />
            </label>
          </div>
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
              Enregistrer
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
              Tester la connexion
            </button>
          </div>
          {feedback ? (
            <div className={feedback.kind === "ok" ? "success" : "error"}>
              {feedback.text}
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}
