import { useId, useState, type FormEvent } from "react";
import { FileText, KeyRound, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  chooseExportDestination,
  formatOperationError,
  processPDF,
  validateExportFileName,
  type ExportProgressState,
} from "../../shared/api";
import { Button, Card, Input, Spinner } from "@internal/ui";
import { ExportProgress } from "../shared/ExportProgress";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";

const minimumPasswordLength = 8;

export function ChangePasswordTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const ownerPasswordId = useId();
  const newPasswordId = useId();
  const confirmPasswordId = useId();
  const outputNameId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [ownerPassword, setOwnerPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [outputName, setOutputName] = useState("password-updated.pdf");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);
  const [exportProgress, setExportProgress] = useState<ExportProgressState>({
    phase: "uploading",
    percentage: 0,
  });

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError(t("files.select"));
      return;
    }
    if (!ownerPassword) {
      setError(t("protect.ownerPasswordRequired"));
      return;
    }
    if (Array.from(newPassword).length < minimumPasswordLength) {
      setError(t("protect.newPasswordTooShort"));
      return;
    }
    if (newPassword !== confirmPassword) {
      setError(t("protect.passwordMismatch"));
      return;
    }
    if (newPassword === ownerPassword) {
      setError(t("protect.passwordsMustDiffer"));
      return;
    }
    const fileName = outputName.trim();
    const nameError = validateExportFileName(fileName);
    if (nameError) {
      setError(t(`exportOptions.${nameError}`));
      return;
    }

    const destinationChoice = chooseExportDestination(fileName, t);
    setWorking(true);
    setExportProgress({ phase: "uploading", percentage: 0 });
    setError("");
    setSuccess(false);
    const data = new FormData();
    data.append("file", file, file.name);
    data.append("owner_password", ownerPassword);
    data.append("new_user_password", newPassword);
    try {
      const destination = await destinationChoice;
      if (destination === null) return;
      const savedName = await processPDF(
        "change-password",
        data,
        fileName,
        t,
        setExportProgress,
        destination,
      );
      setOutputName(savedName);
      setSuccess(true);
    } catch (reason) {
      setError(formatOperationError(reason, t, "errors.passwordChangeFailed"));
    } finally {
      setWorking(false);
      setOwnerPassword("");
      setNewPassword("");
      setConfirmPassword("");
    }
  };

  return (
    <form className="workflow-grid" onSubmit={submit}>
      <Card className="panel">
        <div className="panel-heading">
          <span className="step-number">01</span>
          <div>
            <h2>{t("protect.stepFile")}</h2>
            <p>{t("protect.changeStepFileDescription")}</p>
          </div>
        </div>
        <FileDropzone
          disabled={working}
          onFiles={(incoming) => {
            setFile(incoming[0] ?? null);
            setError("");
            setSuccess(false);
          }}
          onError={setError}
        />
        {file ? (
          <div className="selected-file">
            <span className="file-row-icon">
              <FileText size={17} aria-hidden="true" />
            </span>
            <span className="file-details">
              <span className="file-name">{file.name}</span>
              <span className="file-size">{formatFileSize(file.size, language)}</span>
            </span>
            <Button
              variant="ghost"
              className="icon-button remove-button"
              disabled={working}
              onClick={() => {
                setFile(null);
                setError("");
                setSuccess(false);
              }}
              aria-label={t("files.remove")}
            >
              <X size={16} aria-hidden="true" />
            </Button>
          </div>
        ) : null}
      </Card>

      <Card className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("protect.changeStepPassword")}</h2>
            <p>{t("protect.changeStepPasswordDescription")}</p>
          </div>
        </div>
        <div className="grid gap-3">
          <div>
            <label className="field-label" htmlFor={ownerPasswordId}>
              {t("protect.currentOwnerPassword")}
            </label>
            <Input
              id={ownerPasswordId}
              type="password"
              autoComplete="current-password"
              value={ownerPassword}
              disabled={working}
              onChange={(event) => {
                setOwnerPassword(event.currentTarget.value);
                setError("");
                setSuccess(false);
              }}
            />
          </div>
          <div>
            <label className="field-label" htmlFor={newPasswordId}>
              {t("protect.newOpenPassword")}
            </label>
            <Input
              id={newPasswordId}
              type="password"
              autoComplete="new-password"
              value={newPassword}
              disabled={working}
              onChange={(event) => {
                setNewPassword(event.currentTarget.value);
                setError("");
                setSuccess(false);
              }}
            />
          </div>
          <div>
            <label className="field-label" htmlFor={confirmPasswordId}>
              {t("protect.confirmPassword")}
            </label>
            <Input
              id={confirmPasswordId}
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              disabled={working}
              onChange={(event) => {
                setConfirmPassword(event.currentTarget.value);
                setError("");
                setSuccess(false);
              }}
            />
          </div>
        </div>
        <p className="input-help">{t("protect.permissionsPreserved")}</p>
        <div className="output-preview">
          <span className="output-icon">
            <FileText size={21} aria-hidden="true" />
          </span>
          <span>
            <label className="field-label" htmlFor={outputNameId}>
              {t("exportOptions.fileName")}
            </label>
            <Input
              id={outputNameId}
              value={outputName}
              disabled={working}
              onChange={(event) => {
                setOutputName(event.currentTarget.value);
                setError("");
                setSuccess(false);
              }}
            />
          </span>
        </div>
        <p className="input-help">{t("exportOptions.saveLocationHint")}</p>
        {working ? <ExportProgress progress={exportProgress} /> : null}
        <Button type="submit" disabled={working || !file} className="action-button">
          {working ? <Spinner aria-label={t("common.loading")} /> : <KeyRound size={18} />}
          {working ? t("protect.changeWorking") : t("protect.changeAction")}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("protect.changeSuccess", { fileName: outputName })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}
