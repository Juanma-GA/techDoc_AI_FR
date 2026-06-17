import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { PageHeader } from "../components/PageHeader";
import { RulesCatalog } from "../components/RulesCatalog";
import { resources, type MistralSettingsIn } from "../lib/api";

export function Settings() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["settings", "mistral"],
    queryFn: resources.settings.getMistral,
  });

  const [form, setForm] = useState<MistralSettingsIn>({
    api_key: "",
    base_url: "",
    chat_model: "",
    embed_model: "",
    vision_model: "",
  });
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [testMsg, setTestMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (data) {
      setForm({
        api_key: "",
        base_url: data.base_url,
        chat_model: data.chat_model,
        embed_model: data.embed_model,
        vision_model: data.vision_model,
      });
    }
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: resources.settings.updateMistral,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["settings", "mistral"] });
      setSaveMsg({ ok: true, text: t("settings.saveSuccess") });
      setTimeout(() => setSaveMsg(null), 3000);
    },
    onError: () => setSaveMsg({ ok: false, text: t("errors.generic") }),
  });

  const testMutation = useMutation({
    mutationFn: resources.settings.testMistral,
    onSuccess: (res) => {
      setTestMsg({
        ok: res.ok,
        text: res.ok ? `${t("settings.testSuccess")} — ${res.message}` : `${t("settings.testError")}: ${res.message}`,
      });
      setTimeout(() => setTestMsg(null), 5000);
    },
    onError: () => setTestMsg({ ok: false, text: t("errors.generic") }),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload: MistralSettingsIn = { ...form };
    if (!payload.api_key) delete payload.api_key;
    saveMutation.mutate(payload);
  };

  const field = (
    id: keyof MistralSettingsIn,
    label: string,
    placeholder?: string,
    type = "text",
  ) => (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-fg">
        {label}
        {id === "api_key" && data && (
          <span className={["ml-2 text-xs", data.api_key_set ? "text-green-400" : "text-fg-dim"].join(" ")}>
            {data.api_key_set
              ? `${t("settings.apiKeySet")} (${data.api_key_preview})`
              : t("settings.apiKeyNotSet")}
          </span>
        )}
      </label>
      <input
        id={id}
        type={type}
        value={(form[id] as string) ?? ""}
        onChange={(e) => setForm((f) => ({ ...f, [id]: e.target.value }))}
        placeholder={placeholder}
        className="w-full rounded-md border bg-bg px-3 py-2 text-sm text-fg placeholder-fg-dim focus:outline-none focus:ring-2 focus:ring-brand-blue-light"
      />
    </div>
  );

  return (
    <div className="px-8 py-6">
      <PageHeader
        title={t("routes.settings.title")}
        subtitle={t("routes.settings.subtitle")}
      />

      {isLoading && <p className="text-fg-dim">{t("common.loading")}</p>}

      {!isLoading && (
        <form onSubmit={handleSubmit} className="max-w-lg space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-fg-dim">
            {t("settings.mistral")}
          </h2>

          {field("api_key", t("settings.apiKey"), t("settings.apiKeyPlaceholder"), "password")}
          {field("base_url", t("settings.baseUrl"))}
          {field("chat_model", t("settings.chatModel"))}
          {field("embed_model", t("settings.embedModel"))}
          {field("vision_model", t("settings.visionModel"))}

          {saveMsg && (
            <p className={["text-sm", saveMsg.ok ? "text-green-400" : "text-red-400"].join(" ")}>
              {saveMsg.text}
            </p>
          )}
          {testMsg && (
            <p className={["text-sm", testMsg.ok ? "text-green-400" : "text-red-400"].join(" ")}>
              {testMsg.text}
            </p>
          )}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={saveMutation.isPending}
              className="rounded-md bg-brand px-4 py-2 text-sm font-medium text-fg shadow-card transition-colors hover:bg-brand-blue-light disabled:opacity-50"
            >
              {saveMutation.isPending ? t("common.loading") : t("common.save")}
            </button>
            <button
              type="button"
              onClick={() => testMutation.mutate()}
              disabled={testMutation.isPending}
              className="rounded-md border px-4 py-2 text-sm font-medium text-fg-dim transition-colors hover:text-fg disabled:opacity-50"
            >
              {testMutation.isPending ? t("settings.testing") : t("settings.test")}
            </button>
          </div>
        </form>
      )}
      <div className="mt-8">
        <RulesCatalog />
      </div>
    </div>
  );
}
