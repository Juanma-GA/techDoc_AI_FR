import { useId, useState, type FormEvent } from "react";
import { FileText, LockKeyhole, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  chooseExportDestination,
  formatOperationError,
  processPDF,
  validateExportFileName,
  type ExportProgressState,
} from "../../shared/api";
import { Button, Card, Checkbox, Input, Spinner } from "@internal/ui";
import { ExportProgress } from "../shared/ExportProgress";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";
import { ChangePasswordTool } from "./ChangePasswordTool";

const minimumPasswordLength = 8;

export function ProtectTool() {
  const { t } = useTranslation();
  const [mode, setMode] = useState<"protect" | "change">("protect");

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("protect.operationMode")}>
        <Button
          variant={mode === "protect" ? "primary" : "secondary"}
          aria-pressed={mode === "protect"}
          onClick={() => setMode("protect")}
        >
          {t("protect.modeProtect")}
        </Button>
        <Button
          variant={mode === "change" ? "primary" : "secondary"}
          aria-pressed={mode === "change"}
          onClick={() => setMode("change")}
        >
          {t("protect.modeChange")}
        </Button>
      </div>
      {mode === "protect" ? <ProtectPDFForm /> : <ChangePasswordTool />}
    </div>
  );
}

function ProtectPDFForm() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const filePasswordId = useId();
  const confirmPasswordId = useId();
  const ownerPasswordId = useId();
  const outputNameId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [userPassword, setUserPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [ownerPassword, setOwnerPassword] = useState("");
  const [allowPrint, setAllowPrint] = useState(true);
  const [allowCopy, setAllowCopy] = useState(false);
  const [allowModify, setAllowModify] = useState(false);
  const [allowComments, setAllowComments] = useState(true);
  const [allowFormFill, setAllowFormFill] = useState(true);
  const [allowSign, setAllowSign] = useState(true);
  const [outputName, setOutputName] = useState("protected.pdf");
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
    if (
      Array.from(userPassword).length < minimumPasswordLength ||
      Array.from(ownerPassword).length < minimumPasswordLength
    ) {
      setError(t("protect.passwordTooShort"));
      return;
    }
    if (userPassword !== confirmPassword) {
      setError(t("protect.passwordMismatch"));
      return;
    }
    if (userPassword === ownerPassword) {
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
    data.append("user_password", userPassword);
    data.append("owner_password", ownerPassword);
    data.append("allow_print", String(allowPrint));
    data.append("allow_copy", String(allowCopy));
    data.append("allow_modify", String(allowModify));
    data.append("allow_comments", String(allowComments));
    data.append("allow_form_fill", String(allowFormFill));
    data.append("allow_sign", String(allowSign));
    try {
      const destination = await destinationChoice;
      if (destination === null) return;
      const savedName = await processPDF(
        "protect",
        data,
        fileName,
        t,
        setExportProgress,
        destination,
      );
      setOutputName(savedName);
      setSuccess(true);
    } catch (reason) {
      setError(formatOperationError(reason, t, "errors.protectionFailed"));
    } finally {
      setWorking(false);
      setUserPassword("");
      setConfirmPassword("");
      setOwnerPassword("");
    }
  };

  return (
    <form className="workflow-grid" onSubmit={submit}>
      <Card className="panel">
        <div className="panel-heading">
          <span className="step-number">01</span>
          <div>
            <h2>{t("protect.stepFile")}</h2>
            <p>{t("protect.stepFileDescription")}</p>
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
            <h2>{t("protect.stepSecurity")}</h2>
            <p>{t("protect.stepSecurityDescription")}</p>
          </div>
        </div>
        <div className="grid gap-3">
          <div>
            <label className="field-label" htmlFor={filePasswordId}>
              {t("protect.openPassword")}
            </label>
            <Input
              id={filePasswordId}
              type="password"
              autoComplete="new-password"
              value={userPassword}
              disabled={working}
              onChange={(event) => {
                setUserPassword(event.currentTarget.value);
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
          <div>
            <label className="field-label" htmlFor={ownerPasswordId}>
              {t("protect.ownerPassword")}
            </label>
            <Input
              id={ownerPasswordId}
              type="password"
              autoComplete="new-password"
              value={ownerPassword}
              disabled={working}
              onChange={(event) => {
                setOwnerPassword(event.currentTarget.value);
                setError("");
                setSuccess(false);
              }}
            />
            <small>{t("protect.passwordHelp")}</small>
          </div>
        </div>
        <fieldset className="grid gap-3">
          <legend className="field-label">{t("protect.permissions")}</legend>
          {(
            [
              ["Print", allowPrint, setAllowPrint],
              ["Copy", allowCopy, setAllowCopy],
              ["Modify", allowModify, setAllowModify],
              ["Comments", allowComments, setAllowComments],
              ["FormFill", allowFormFill, setAllowFormFill],
              ["Sign", allowSign, setAllowSign],
            ] as const
          ).map(([permission, checked, onCheckedChange]) => (
            <div className="flex items-center gap-2" key={permission}>
              <Checkbox
                checked={checked}
                onCheckedChange={onCheckedChange}
                disabled={working}
                aria-label={t(`protect.allow${permission}`)}
              />
              <span>{t(`protect.allow${permission}`)}</span>
            </div>
          ))}
        </fieldset>
        <p className="input-help">{t("protect.permissionsWarning")}</p>
        <p className="input-help">{t("protect.formSignaturePermissionNote")}</p>
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
          {working ? <Spinner aria-label={t("common.loading")} /> : <LockKeyhole size={18} />}
          {working ? t("protect.working") : t("protect.action")}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("protect.success", { fileName: outputName })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}
