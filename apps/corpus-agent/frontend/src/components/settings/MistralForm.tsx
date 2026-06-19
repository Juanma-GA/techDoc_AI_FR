import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { settingsApi } from "../../lib/api";
import type { MistralSettingsOut } from "../../lib/types";

export function MistralForm() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [form, setForm] = useState({ api_key: "", base_url: "", chat_model: "", embed_model: "", vision_model: "" });
  const [feedback, setFeedback] = useState<{ ok: boolean; msg: string } | null>(null);

  const settingsQuery = useQuery<MistralSettingsOut>({ queryKey: ["mistral-settings"], queryFn: settingsApi.read });
  const s = settingsQuery.data;
  useEffect(() => {
    if (s) setForm({ api_key: "", base_url: s.base_url, chat_model: s.chat_model, embed_model: s.embed_model, vision_model: s.vision_model });
  }, [s]);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["mistral-settings"] });
    void qc.invalidateQueries({ queryKey: ["health"] });
  };

  const toggleLlm = useMutation({
    mutationFn: (llm_enabled: boolean) => settingsApi.write({ llm_enabled }),
    onSuccess: invalidate,
  });
  const save = useMutation({
    mutationFn: () =>
      settingsApi.write({
        ...(form.api_key ? { api_key: form.api_key } : {}),
        base_url: form.base_url,
        chat_model: form.chat_model,
        embed_model: form.embed_model,
        vision_model: form.vision_model,
      }),
    onSuccess: () => {
      setForm((f) => ({ ...f, api_key: "" }));
      invalidate();
    },
  });
  const test = useMutation({
    mutationFn: () => settingsApi.test(),
    onSuccess: (res) => {
      setFeedback({ ok: res.ok, msg: res.message });
      invalidate();
    },
  });

  return (
    <div className="card">
      <h2 className="card-title">{t("settings.ai")}</h2>
      <div className="switch-row">
        <div>
          <div>{t("settings.llmEnabled")}</div>
          <div className="label">{t("settings.llmEnabledHint")}</div>
        </div>
        <label className="switch">
          <input type="checkbox" checked={!!s?.llm_enabled} onChange={(e) => toggleLlm.mutate(e.target.checked)} />
          <span className="track" />
        </label>
      </div>

      <h2 className="card-title" style={{ marginTop: 16 }}>{t("settings.mistral")}</h2>
      <form className="form" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        <label className="label">{t("settings.apiKey")}</label>
        <input
          className="input"
          type="password"
          value={form.api_key}
          placeholder={s?.api_key_set ? s.api_key_preview || t("settings.apiKeyPh") : t("settings.apiKeyPh")}
          onChange={(e) => setForm({ ...form, api_key: e.target.value })}
        />
        <label className="label">{t("settings.baseUrl")}</label>
        <input className="input" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} />
        <label className="label">{t("settings.chatModel")}</label>
        <input className="input" value={form.chat_model} onChange={(e) => setForm({ ...form, chat_model: e.target.value })} />
        <label className="label">{t("settings.embedModel")}</label>
        <input className="input" value={form.embed_model} onChange={(e) => setForm({ ...form, embed_model: e.target.value })} />
        <label className="label">{t("settings.visionModel")}</label>
        <input className="input" value={form.vision_model} onChange={(e) => setForm({ ...form, vision_model: e.target.value })} />
        <div className="row">
          <button type="submit" className="btn primary" disabled={save.isPending}>{t("common.save")}</button>
          <button type="button" className="btn secondary" onClick={() => test.mutate()} disabled={test.isPending}>
            {test.isPending ? <span className="spinner" /> : null} {t("settings.test")}
          </button>
          {feedback && <span className={feedback.ok ? "success" : "error"}>{feedback.msg}</span>}
        </div>
      </form>
    </div>
  );
}
