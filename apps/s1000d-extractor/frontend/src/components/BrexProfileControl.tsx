import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { brexApi, type S1000dIssue } from "../lib/api";
import { BrexRulesPreview } from "./BrexRulesPreview";

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
  const fileInput = useRef<HTMLInputElement>(null);
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
      if (fileInput.current) fileInput.current.value = "";
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : String(error));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="brex-profile-control form">
      <div className="label">{t("migration.brex.addProfileTitle")}</div>
      <label>
        <div className="label">{t("migration.brex.file")}</div>
        <input
          ref={fileInput}
          className="input"
          type="file"
          accept=".xml"
          disabled={disabled || uploading}
          onChange={(event) => {
            const selectedFile = event.target.files?.[0] ?? null;
            setFile(selectedFile);
            setProfileName(selectedFile?.name.replace(/\.[^.]+$/, "") ?? "");
            setUploadError(null);
          }}
        />
      </label>
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

      <label>
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
