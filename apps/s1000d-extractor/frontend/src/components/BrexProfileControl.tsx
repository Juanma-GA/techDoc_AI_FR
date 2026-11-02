import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { FileDropzone } from "@internal/ui";
import { FileText } from "lucide-react";

import { brexApi, type S1000dIssue } from "../lib/api";
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
  const [file, setFile] = useState<File | null>(null);
  const [profileName, setProfileName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

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

  const uploadProfile = async () => {
    if (!file) {
      setUploadError(t("migration.brex.noFile"));
      return;
    }
    if (!profileName.trim()) {
      setUploadError(t("migration.brex.noName"));
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      const created = await brexApi.upload(file, profileName.trim(), issue);
      await queryClient.invalidateQueries({ queryKey: ["s1000d-brex"] });
      onChange(created.id);
      setFile(null);
      setProfileName("");
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : String(error));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="brex-profile-control form">
      <div className="label">{t("migration.brex.addProfileTitle")}</div>
      <div className="space-y-2">
        <span className="block text-label font-mono uppercase text-fg-dim">
          {t("migration.brex.file")}
        </span>
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
              setFile(null);
              setProfileName("");
              setUploadError(t("migration.ui.invalidFile"));
              return;
            }
            setFile(selectedFile);
            setProfileName(selectedFile.name.replace(/\.[^.]+$/, ""));
            setUploadError(null);
          }}
        />
        {file ? (
          <div className="flex items-center gap-2 rounded-sm border bg-bg-2 px-3 py-1.5" role="status">
            <FileText size={16} className="shrink-0 text-fg-dim" aria-hidden="true" />
            <span className="min-w-0 flex-1 truncate text-sm" title={file.name}>
              {file.name}
            </span>
          </div>
        ) : null}
      </div>
      <div className="row">
        <label className="grow">
          <div className="label">{t("migration.brex.profileName")}</div>
          <input
            className="input"
            type="text"
            value={profileName}
            disabled={disabled || uploading}
            onChange={(event) => setProfileName(event.target.value)}
          />
        </label>
        <button
          type="button"
          className="btn secondary"
          disabled={disabled || uploading || !file || !profileName.trim()}
          onClick={() => void uploadProfile()}
        >
          {uploading ? t("migration.brex.uploading") : t("migration.brex.add")}
        </button>
      </div>
      {uploadError ? <div className="error" role="alert">{uploadError}</div> : null}

      <div className="row">
        <label className="grow">
          <div className="label">{t("migration.upload.brex")}</div>
          <select
            className="input"
            value={value ?? ""}
            disabled={disabled || profilesQuery.isLoading}
            onChange={(event) => onChange(event.target.value || null)}
          >
            <option value="">{t("migration.brex.none")}</option>
            {(profilesQuery.data ?? []).map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name} — {t("migration.upload.issueValue", { issue: profile.s1000d_issue })}
              </option>
            ))}
          </select>
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
        <div className="label" role="status">{t("migration.brex.loading")}</div>
      ) : null}
      {profilesQuery.isError ? (
        <div className="error" role="alert">
          {t("migration.brex.listError", {
            message: profilesQuery.error instanceof Error
              ? profilesQuery.error.message
              : String(profilesQuery.error),
          })}
        </div>
      ) : null}
      {profileMissing ? (
        <div className="error" role="alert">{t("migration.brex.profileMissing")}</div>
      ) : null}
      {issueMismatch && selectedProfile ? (
        <div className="error" role="alert">
          {t("migration.brex.issueMismatch", {
            brexIssue: selectedProfile.s1000d_issue,
            dmIssue: issue,
          })}
        </div>
      ) : null}

      {value && detailQuery.isLoading ? (
        <div className="label" role="status">{t("migration.brex.loadingRules")}</div>
      ) : null}
      {value && detailQuery.isError ? (
        <div className="error" role="alert">
          {t("migration.brex.rulesError", {
            message: detailQuery.error instanceof Error
              ? detailQuery.error.message
              : String(detailQuery.error),
          })}
        </div>
      ) : null}
      {detailQuery.data ? <BrexRulesPreview profile={detailQuery.data} /> : null}
    </div>
  );
}
