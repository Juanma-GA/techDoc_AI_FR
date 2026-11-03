import { zodResolver } from "@hookform/resolvers/zod";
import { Button, Input, Spinner } from "@internal/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderInput, FolderOutput, RefreshCw, Save, Search } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { DataResetCard } from "../components/business/DataResetCard";
import { browseApi, settingsApi } from "../lib/api";

const schema = z.object({
  onedrive_input_root: z.string().trim(),
  onedrive_output_root: z.string().trim(),
  composer_license_server: z.string().trim(),
  composer_converter_path: z.string().trim(),
  composer_settings_path: z.string().trim(),
});
type FormValues = z.infer<typeof schema>;

export function Settings() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [saved, setSaved] = useState(false);
  const [detected, setDetected] = useState<string[]>([]);
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: settingsApi.read });

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    getValues,
    formState: { isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      onedrive_input_root: "",
      onedrive_output_root: "",
      composer_license_server: "",
      composer_converter_path: "",
      composer_settings_path: "",
    },
    values: settingsQuery.data,
  });

  const saveMutation = useMutation({
    mutationFn: (values: FormValues) => settingsApi.write(values),
    onSuccess: (data) => {
      qc.setQueryData(["settings"], data);
      reset(data);
      setSaved(true);
      void qc.invalidateQueries({ queryKey: ["browse", "roots"] });
      void qc.invalidateQueries({ queryKey: ["composer-status"] });
    },
  });

  const detectMutation = useMutation({
    mutationFn: () => browseApi.roots(),
    onSuccess: (data) => {
      setDetected(data.detected);
      if (!getValues("onedrive_input_root") && data.detected[0]) {
        setValue("onedrive_input_root", data.detected[0], { shouldDirty: true });
        setSaved(false);
      }
    },
  });

  if (settingsQuery.isLoading) return <Spinner aria-label={t("settings.loading")} />;
  if (settingsQuery.isError) {
    return (
      <div className="space-y-4">
        <p role="alert" className="error">{settingsQuery.error.message}</p>
        <Button variant="secondary" onClick={() => void settingsQuery.refetch()}>
          <RefreshCw size={16} aria-hidden="true" />
          {t("settings.retry")}
        </Button>
      </div>
    );
  }

  return (
    <div className="min-w-0 max-w-4xl space-y-8">
      <form
        className="space-y-6"
        onChange={() => setSaved(false)}
        onSubmit={handleSubmit((values) => {
          setSaved(false);
          saveMutation.mutate(values);
        })}
      >
        <section className="min-w-0 space-y-4 pb-6" aria-labelledby="onedrive-title">
          <h2 id="onedrive-title" className="text-base font-semibold">{t("settings.onedriveTitle")}</h2>
          <div className="grid min-w-0 gap-4 md:grid-cols-2">
          <div className="field">
            <label htmlFor="od_input" className="field-label">
              {t("settings.onedriveInput")}
            </label>
            <Input
              id="od_input"
              {...register("onedrive_input_root")}
            />
          </div>
          <div className="field">
            <label htmlFor="od_output" className="field-label">
              {t("settings.onedriveOutput")}
            </label>
            <Input
              id="od_output"
              {...register("onedrive_output_root")}
            />
          </div>
          </div>
          <Button variant="secondary" onClick={() => detectMutation.mutate()} disabled={detectMutation.isPending}>
            {detectMutation.isPending ? <Spinner aria-label={t("settings.loading")} /> : <Search size={16} aria-hidden="true" />}
            {t("settings.onedriveDetect")}
          </Button>
          {detectMutation.isError ? <p role="alert" className="error">{detectMutation.error.message}</p> : null}
          {detected.length ? (
            <ul className="min-w-0">
              {detected.map((path) => (
                <li key={path} className="grid min-w-0 gap-3 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                  <code className="break-all text-xs">{path}</code>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" onClick={() => {
                      setValue("onedrive_input_root", path, { shouldDirty: true });
                      setSaved(false);
                    }}>
                      <FolderInput size={16} aria-hidden="true" />
                      {t("settings.onedriveUseInput")}
                    </Button>
                    <Button variant="secondary" size="sm" onClick={() => {
                      setValue("onedrive_output_root", path, { shouldDirty: true });
                      setSaved(false);
                    }}>
                      <FolderOutput size={16} aria-hidden="true" />
                      {t("settings.onedriveUseOutput")}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
        <section className="min-w-0 space-y-4 pb-6" aria-labelledby="composer-title">
          <h2 id="composer-title" className="text-base font-semibold">{t("settings.composerTitle")}</h2>
          <div className="field">
            <label htmlFor="lic_server" className="field-label">
              {t("settings.composerLicense")}
            </label>
            <Input
              className="font-mono"
              id="lic_server"
              placeholder="4085@serveur-licence"
              aria-describedby="license-hint"
              {...register("composer_license_server")}
            />
            <p id="license-hint" className="hint">{t("settings.composerHint")}</p>
          </div>
          <div className="field">
            <label htmlFor="composer_executable" className="field-label">{t("conversion.composerExecutable")}</label>
            <Input id="composer_executable" aria-describedby="executable-hint" {...register("composer_converter_path")} />
            <p id="executable-hint" className="hint">{t("conversion.composerExecutableHint")}</p>
          </div>
          <div className="field">
            <label htmlFor="composer_profile" className="field-label">{t("conversion.composerSettings")}</label>
            <Input id="composer_profile" aria-describedby="profile-hint" {...register("composer_settings_path")} />
            <p id="profile-hint" className="hint">{t("conversion.composerSettingsHint")}</p>
          </div>
        </section>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={saveMutation.isPending || !isDirty}>
            {saveMutation.isPending ? <Spinner aria-label={t("settings.loading")} /> : <Save size={16} aria-hidden="true" />}
            {t("settings.save")}
          </Button>
          {saved ? <p role="status" className="text-sm text-success">{t("settings.saved")}</p> : null}
        </div>
        {saveMutation.isError ? <p role="alert" className="error">{saveMutation.error.message}</p> : null}
      </form>
      <DataResetCard
        title={t("settings.deleteUserDataTitle")}
        description={t("settings.deleteUserDataHint")}
      />
    </div>
  );
}
