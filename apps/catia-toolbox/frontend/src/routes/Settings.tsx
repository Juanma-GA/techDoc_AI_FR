import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { browseApi, settingsApi, type SettingsDto, type TestConnectionDto } from "../lib/api";

const schema = z.object({
  api_key: z.string().optional(),
  base_url: z.string().url().or(z.literal("")),
  chat_model: z.string().min(1),
  embed_model: z.string().min(1),
});
type FormValues = z.infer<typeof schema>;

export function Settings() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<TestConnectionDto | null>(null);
  const [llmNotice, setLlmNotice] = useState<string | null>(null);

  const settingsQuery = useQuery<SettingsDto>({ queryKey: ["settings"], queryFn: settingsApi.read });

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    values: settingsQuery.data
      ? {
          api_key: "",
          base_url: settingsQuery.data.base_url,
          chat_model: settingsQuery.data.chat_model,
          embed_model: settingsQuery.data.embed_model,
        }
      : undefined,
  });

  const llmMutation = useMutation({
    mutationFn: (enabled: boolean) => settingsApi.write({ llm_enabled: enabled }),
    onSuccess: (data) => {
      setLlmNotice(data.llm_enabled ? t("settings.llmTitle") : null);
      void qc.invalidateQueries({ queryKey: ["settings"] });
      void qc.invalidateQueries({ queryKey: ["health"] });
    },
  });

  const saveMutation = useMutation({
    mutationFn: (values: FormValues) =>
      settingsApi.write({
        api_key: values.api_key ? values.api_key : undefined,
        base_url: values.base_url || undefined,
        chat_model: values.chat_model,
        embed_model: values.embed_model,
      }),
    onSuccess: (data) => {
      setSavedNotice(t("settings.saved"));
      reset({ api_key: "", base_url: data.base_url, chat_model: data.chat_model, embed_model: data.embed_model });
      void qc.invalidateQueries({ queryKey: ["settings"] });
      void qc.invalidateQueries({ queryKey: ["health"] });
    },
  });

  const testMutation = useMutation({
    mutationFn: () => settingsApi.test(),
    onSuccess: (data) => {
      setTestResult(data);
      void qc.invalidateQueries({ queryKey: ["health"] });
    },
  });

  const [odInput, setOdInput] = useState("");
  const [odOutput, setOdOutput] = useState("");
  const [odNotice, setOdNotice] = useState<string | null>(null);
  const [detected, setDetected] = useState<string[]>([]);

  useEffect(() => {
    if (settingsQuery.data) {
      setOdInput(settingsQuery.data.onedrive_input_root || "");
      setOdOutput(settingsQuery.data.onedrive_output_root || "");
    }
  }, [settingsQuery.data]);

  const odSaveMutation = useMutation({
    mutationFn: () =>
      settingsApi.write({ onedrive_input_root: odInput.trim(), onedrive_output_root: odOutput.trim() }),
    onSuccess: () => {
      setOdNotice(t("settings.saved"));
      void qc.invalidateQueries({ queryKey: ["settings"] });
      void qc.invalidateQueries({ queryKey: ["browse", "roots"] });
    },
  });

  const detectMutation = useMutation({
    mutationFn: () => browseApi.roots(),
    onSuccess: (data) => {
      setDetected(data.detected);
      if (!odInput.trim() && data.detected[0]) setOdInput(data.detected[0]);
    },
  });

  if (settingsQuery.isLoading) return <span className="spinner" />;
  const apiKeySet = settingsQuery.data?.api_key_set ?? false;
  const llmEnabled = settingsQuery.data?.llm_enabled ?? false;

  return (
    <div className="form" style={{ maxWidth: "42rem" }}>
      <article className="card">
        <h2 className="card-title">{t("settings.llmTitle")}</h2>
        <div className="switch-row">
          <div>
            <div className="label">{t("settings.llmEnabled")}</div>
            <p className="hint">{t("settings.llmHint")}</p>
          </div>
          <label className="switch">
            <input
              type="checkbox"
              aria-label={t("settings.llmEnabled")}
              checked={llmEnabled}
              disabled={llmMutation.isPending}
              onChange={(e) => {
                setLlmNotice(null);
                llmMutation.mutate(e.target.checked);
              }}
            />
            <span className="track" />
          </label>
        </div>
        {llmNotice ? <p className="success">{llmNotice}</p> : null}
      </article>

      <article className="card">
        <h2 className="card-title">
          <span className="row">
            <span>Mistral</span>
            {apiKeySet ? (
              <span className="badge ok">CONFIGURED</span>
            ) : (
              <span className="badge warn">NOT CONFIGURED</span>
            )}
          </span>
        </h2>
        <form
          onSubmit={handleSubmit((v) => {
            setSavedNotice(null);
            saveMutation.mutate(v);
          })}
          className="form"
        >
          <div className="field">
            <label htmlFor="api_key" className="field-label">
              {t("settings.apiKeyLabel")}
            </label>
            <input
              className="input mono"
              id="api_key"
              type="password"
              autoComplete="off"
              placeholder="sk-..."
              {...register("api_key")}
            />
            {apiKeySet ? <p className="hint">{t("settings.apiKeyStored")}</p> : null}
          </div>
          <div className="field">
            <label htmlFor="base_url" className="field-label">
              {t("settings.baseUrlLabel")}
            </label>
            <input className="input" id="base_url" {...register("base_url")} />
          </div>
          <div className="grid-2">
            <div className="field">
              <label htmlFor="chat_model" className="field-label">
                {t("settings.chatModelLabel")}
              </label>
              <input className="input" id="chat_model" {...register("chat_model")} />
            </div>
            <div className="field">
              <label htmlFor="embed_model" className="field-label">
                {t("settings.embedModelLabel")}
              </label>
              <input className="input" id="embed_model" {...register("embed_model")} />
            </div>
          </div>
          <div className="row">
            <button type="submit" className="btn primary" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? <span className="spinner" /> : null}
              <span>{t("settings.save")}</span>
            </button>
            <button
              type="button"
              className="btn secondary"
              onClick={() => {
                setTestResult(null);
                testMutation.mutate();
              }}
              disabled={testMutation.isPending}
            >
              {testMutation.isPending ? <span className="spinner" /> : null}
              <span>{t("settings.test")}</span>
            </button>
          </div>
          {savedNotice ? <p className="success">{savedNotice}</p> : null}
          {testResult ? (
            <p className={testResult.ok ? "success" : "error"}>
              {testResult.ok
                ? t("settings.testOk", { count: testResult.models.length })
                : t("settings.testFailed", { error: testResult.error ?? "" })}
            </p>
          ) : null}
        </form>
      </article>

      <article className="card">
        <h2 className="card-title">{t("settings.onedriveTitle")}</h2>
        <p className="banner info">{t("settings.onedriveNotice")}</p>
        <div className="form">
          <div className="field">
            <label htmlFor="od_input" className="field-label">
              {t("settings.onedriveInput")}
            </label>
            <input
              className="input"
              id="od_input"
              value={odInput}
              onChange={(e) => setOdInput(e.target.value)}
              placeholder="C:\\Users\\moi\\OneDrive - Entreprise\\CATIA"
            />
          </div>
          <div className="field">
            <label htmlFor="od_output" className="field-label">
              {t("settings.onedriveOutput")}
            </label>
            <input
              className="input"
              id="od_output"
              value={odOutput}
              onChange={(e) => setOdOutput(e.target.value)}
              placeholder="C:\\Users\\moi\\OneDrive - Entreprise\\CATIA\\exports"
            />
          </div>
          <div className="row">
            <button type="button" className="btn primary" onClick={() => odSaveMutation.mutate()} disabled={odSaveMutation.isPending}>
              {odSaveMutation.isPending ? <span className="spinner" /> : null}
              <span>{t("settings.save")}</span>
            </button>
            <button type="button" className="btn secondary" onClick={() => detectMutation.mutate()} disabled={detectMutation.isPending}>
              {detectMutation.isPending ? <span className="spinner" /> : null}
              <span>{t("settings.onedriveDetect")}</span>
            </button>
          </div>
          {odNotice ? <p className="success">{odNotice}</p> : null}
          {detected.length ? (
            <ul className="item-list">
              {detected.map((d) => (
                <li key={d} className="item-row">
                  <code className="item-main mono" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d}</code>
                  <div className="item-actions">
                    <button type="button" className="btn ghost small" onClick={() => setOdInput(d)}>
                      {t("settings.onedriveUseInput")}
                    </button>
                    <button type="button" className="btn ghost small" onClick={() => setOdOutput(d)}>
                      {t("settings.onedriveUseOutput")}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </article>
    </div>
  );
}
