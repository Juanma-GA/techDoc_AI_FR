import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button, FileDropzone, Input, Select } from "@internal/ui";
import { useTranslation } from "react-i18next";
import { FileText } from "lucide-react";

import { brexApi, type S1000dIssue } from "../lib/api";
import { formatApiError } from "../lib/migrationUtils";
import { BrexRulesPreview } from "./BrexRulesPreview";
import { BrexProfileDeleteAction } from "./BrexProfileDeleteAction";

type Props = {
  issue: S1000dIssue;
  value: string | null;
  onChange: (id: string | null) => void;
  onReadyChange: (ready: boolean) => void;
  disabled?: boolean;
};

export function BrexProfileControl({
  issue,
  value,
  onChange,
  onReadyChange,
  disabled = false,
}: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const schema = useMemo(() => z.object({
    file: z.instanceof(File).nullable().superRefine((file, context) => {
      if (!file) {
        context.addIssue({ code: z.ZodIssueCode.custom, message: t("migration.brex.noFile") });
      } else if (!/\.xml$/i.test(file.name)) {
        context.addIssue({ code: z.ZodIssueCode.custom, message: t("migration.ui.invalidFile") });
      }
    }),
    profileName: z.string().trim().min(1, t("migration.brex.noName")),
  }), [t]);
  const { control, register, handleSubmit, setValue, formState } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { file: null, profileName: "" },
  });

  const profilesQuery = useQuery({
    queryKey: ["s1000d-brex"],
    queryFn: brexApi.list,
  });
  const detailQuery = useQuery({
    queryKey: ["s1000d-brex", value],
    queryFn: () => {
      if (!value) throw new Error("BREX profile ID is required.");
      return brexApi.detail(value);
    },
    enabled: Boolean(value),
  });

  const selectedProfile = profilesQuery.data?.find((profile) => profile.id === value);
  const issueMismatch = Boolean(selectedProfile && selectedProfile.s1000d_issue !== issue);
  const profileMissing = Boolean(value && profilesQuery.isSuccess && !selectedProfile);
  const ready =
    !value ||
    (profilesQuery.isSuccess &&
      Boolean(selectedProfile) &&
      detailQuery.isSuccess &&
      !issueMismatch);

  useEffect(() => {
    onReadyChange(ready);
  }, [onReadyChange, ready]);

  const uploadProfile = handleSubmit(async ({ file: selectedFile, profileName: name }) => {
    if (!selectedFile) {
      setUploadError(t("migration.brex.noFile"));
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      const created = await brexApi.upload(selectedFile, name, issue);
      await queryClient.invalidateQueries({ queryKey: ["s1000d-brex"] });
      onChange(created.id);
      setValue("file", null);
      setValue("profileName", "");
    } catch (error) {
      setUploadError(formatApiError(t, error));
    } finally {
      setUploading(false);
    }
  });

  return (
    <div className="brex-profile-control space-y-3">
      <div className="text-label font-mono uppercase text-fg-dim">
        {t("migration.brex.addProfileTitle")}
      </div>
      <form className="space-y-3" noValidate onSubmit={uploadProfile}>
        <div className="space-y-2">
          <span className="block text-label font-mono uppercase text-fg-dim">
            {t("migration.brex.file")}
          </span>
          <Controller control={control} name="file" render={({ field }) =>
            <>
              <FileDropzone
                accept=".xml"
                multiple={false}
                disabled={disabled || uploading}
                className="p-4"
                label={t("migration.upload.dropLabel")}
                description="XML"
                onFiles={(files) => {
                  const selectedFile = files[0];
                  if (!selectedFile) return;
                  if (!/\.xml$/i.test(selectedFile.name)) {
                    field.onChange(null);
                    setValue("profileName", "");
                    setUploadError(t("migration.ui.invalidFile"));
                    return;
                  }
                  field.onChange(selectedFile);
                  field.onBlur();
                  setUploadError(null);
                  setValue("profileName", selectedFile.name.replace(/\.[^.]+$/, ""));
                }}
              />
              {field.value?.name ? (
                <div className="flex items-center gap-2 rounded-sm border bg-bg-2 px-3 py-1.5" role="status">
                  <FileText size={16} className="shrink-0 text-fg-dim" aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate text-sm" title={field.value.name}>
                    {field.value.name}
                  </span>
                </div>
              ) : null}
            </>
          } />
          {formState.errors.file ? <span role="alert" className="block text-sm text-danger">
            {formState.errors.file.message}
          </span> : null}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-0 flex-1 space-y-2">
            <span className="block text-label font-mono uppercase text-fg-dim">
              {t("migration.brex.profileName")}
            </span>
            <Input
              type="text"
              {...register("profileName")}
              disabled={disabled || uploading}
            />
            {formState.errors.profileName ? <span role="alert" className="block text-sm text-danger">
              {formState.errors.profileName.message}
            </span> : null}
          </label>
          <Button
            type="submit"
            variant="secondary"
            size="sm"
            disabled={disabled || uploading || formState.isSubmitting}
          >
            {uploading ? t("migration.brex.uploading") : t("migration.brex.add")}
          </Button>
        </div>
        {uploadError ? <div className="text-sm text-danger" role="alert">{uploadError}</div> : null}
      </form>

      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-0 flex-1 space-y-2">
          <span className="block text-label font-mono uppercase text-fg-dim">
            {t("migration.upload.brex")}
          </span>
          <Select
            value={value ?? ""}
            disabled={disabled || profilesQuery.isLoading}
            onChange={(event) => onChange(event.target.value || null)}
            options={[
              { value: "", label: t("migration.brex.none") },
              ...(profilesQuery.data ?? []).map((profile) => ({
                value: profile.id,
                label: `${profile.name} — ${t("migration.upload.issueValue", { issue: profile.s1000d_issue })}`,
              })),
            ]}
          />
        </label>
        {selectedProfile ? (
          <BrexProfileDeleteAction
            key={selectedProfile.id}
            profileId={selectedProfile.id}
            disabled={disabled || profilesQuery.isLoading}
            onDeleted={(deletedId) => {
              if (value === deletedId) onChange(null);
            }}
          />
        ) : null}
      </div>

      {profilesQuery.isLoading ? (
        <div className="text-sm text-fg-dim" role="status">{t("migration.brex.loading")}</div>
      ) : null}
      {profilesQuery.isError ? (
        <div className="text-sm text-danger" role="alert">
          {t("migration.brex.listError", {
            message: formatApiError(t, profilesQuery.error),
          })}
        </div>
      ) : null}
      {profileMissing ? (
        <div className="text-sm text-danger" role="alert">{t("migration.brex.profileMissing")}</div>
      ) : null}
      {issueMismatch && selectedProfile ? (
        <div className="text-sm text-danger" role="alert">
          {t("migration.brex.issueMismatch", {
            brexIssue: selectedProfile.s1000d_issue,
            dmIssue: issue,
          })}
        </div>
      ) : null}

      {value && detailQuery.isLoading ? (
        <div className="text-sm text-fg-dim" role="status">{t("migration.brex.loadingRules")}</div>
      ) : null}
      {value && detailQuery.isError ? (
        <div className="text-sm text-danger" role="alert">
          {t("migration.brex.rulesError", {
            message: formatApiError(t, detailQuery.error),
          })}
        </div>
      ) : null}
      {detailQuery.data ? <BrexRulesPreview profile={detailQuery.data} /> : null}
    </div>
  );
}
