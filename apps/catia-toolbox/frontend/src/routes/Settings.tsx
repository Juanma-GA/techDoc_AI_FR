import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Spinner } from "@internal/ui";
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
    },
  });

  const testMutation = useMutation({
    mutationFn: () => settingsApi.test(),
    onSuccess: (data) => setTestResult(data),
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

  if (settingsQuery.isLoading) return <Spinner />;
  const apiKeySet = settingsQuery.data?.api_key_set ?? false;

  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <header>
        <h1 className="font-display text-xl text-fg">{t("settings.title")}</h1>
        <p className="text-fg-dim">{t("settings.subtitle")}</p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>
            <span className="flex items-center gap-2">
              <span>Mistral</span>
              {apiKeySet ? (
                <Badge variant="success">configured</Badge>
              ) : (
                <Badge variant="warning">not configured</Badge>
              )}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleSubmit((v) => {
              setSavedNotice(null);
              saveMutation.mutate(v);
            })}
            className="flex flex-col gap-3"
          >
            <div>
              <label htmlFor="api_key" className="label">
                {t("settings.apiKeyLabel")}
              </label>
              <Input id="api_key" type="password" autoComplete="off" placeholder="sk-..." {...register("api_key")} />
              {apiKeySet ? <p className="mt-1 text-xs text-fg-dim">{t("settings.apiKeyStored")}</p> : null}
            </div>
            <div>
              <label htmlFor="base_url" className="label">
                {t("settings.baseUrlLabel")}
              </label>
              <Input id="base_url" state={errors.base_url ? "error" : "default"} {...register("base_url")} />
            </div>
            <div>
              <label htmlFor="chat_model" className="label">
                {t("settings.chatModelLabel")}
              </label>
              <Input id="chat_model" state={errors.chat_model ? "error" : "default"} {...register("chat_model")} />
            </div>
            <div>
              <label htmlFor="embed_model" className="label">
                {t("settings.embedModelLabel")}
              </label>
              <Input id="embed_model" state={errors.embed_model ? "error" : "default"} {...register("embed_model")} />
            </div>
            <div className="flex items-center gap-2">
              <Button type="submit" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? <Spinner size="sm" /> : null}
                <span>{t("settings.save")}</span>
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setTestResult(null);
                  testMutation.mutate();
                }}
                disabled={testMutation.isPending}
              >
                {testMutation.isPending ? <Spinner size="sm" /> : null}
                <span>{t("settings.test")}</span>
              </Button>
            </div>
            {savedNotice ? <p className="text-sm text-success">{savedNotice}</p> : null}
            {testResult ? (
              <p className={testResult.ok ? "text-sm text-success" : "text-sm text-danger"}>
                {testResult.ok
                  ? t("settings.testOk", { count: testResult.models.length })
                  : t("settings.testFailed", { error: testResult.error ?? "" })}
              </p>
            ) : null}
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.onedriveTitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 rounded-sm border border-info/40 bg-info/10 px-3 py-2 text-sm text-fg-dim">
            {t("settings.onedriveNotice")}
          </p>
          <div className="flex flex-col gap-3">
            <div>
              <label htmlFor="od_input" className="label">
                {t("settings.onedriveInput")}
              </label>
              <Input
                id="od_input"
                value={odInput}
                onChange={(e) => setOdInput(e.target.value)}
                placeholder="C:\\Users\\moi\\OneDrive - Entreprise\\CATIA"
              />
            </div>
            <div>
              <label htmlFor="od_output" className="label">
                {t("settings.onedriveOutput")}
              </label>
              <Input
                id="od_output"
                value={odOutput}
                onChange={(e) => setOdOutput(e.target.value)}
                placeholder="C:\\Users\\moi\\OneDrive - Entreprise\\CATIA\\exports"
              />
            </div>
            <div className="flex items-center gap-2">
              <Button type="button" onClick={() => odSaveMutation.mutate()} disabled={odSaveMutation.isPending}>
                {odSaveMutation.isPending ? <Spinner size="sm" /> : null}
                <span>{t("settings.save")}</span>
              </Button>
              <Button type="button" variant="secondary" onClick={() => detectMutation.mutate()} disabled={detectMutation.isPending}>
                {detectMutation.isPending ? <Spinner size="sm" /> : null}
                <span>{t("settings.onedriveDetect")}</span>
              </Button>
            </div>
            {odNotice ? <p className="text-sm text-success">{odNotice}</p> : null}
            {detected.length ? (
              <ul className="flex flex-col gap-1">
                {detected.map((d) => (
                  <li key={d} className="flex items-center gap-2 text-sm">
                    <code className="flex-1 truncate text-fg-dim">{d}</code>
                    <Button variant="ghost" size="sm" onClick={() => setOdInput(d)}>
                      {t("settings.onedriveUseInput")}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => setOdOutput(d)}>
                      {t("settings.onedriveUseOutput")}
                    </Button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
