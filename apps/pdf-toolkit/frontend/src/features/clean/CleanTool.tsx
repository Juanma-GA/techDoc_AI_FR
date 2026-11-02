import { useId, useState, type FormEvent } from "react";
import { Eraser, FileText, X } from "lucide-react";
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

export function CleanTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const outputNameId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [outputName, setOutputName] = useState("cleaned.pdf");
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
    try {
      const destination = await destinationChoice;
      if (destination === null) return;
      const savedName = await processPDF(
        "clean",
        data,
        fileName,
        t,
        setExportProgress,
        destination,
      );
      setOutputName(savedName);
      setSuccess(true);
    } catch (reason) {
      setError(formatOperationError(reason, t, "errors.cleanFailed"));
    } finally {
      setWorking(false);
    }
  };

  return (
    <form className="workflow-grid" onSubmit={submit}>
      <Card className="panel">
        <div className="panel-heading">
          <span className="step-number">01</span>
          <div>
            <h2>{t("clean.stepFile")}</h2>
            <p>{t("clean.stepFileDescription")}</p>
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
        <p className="privacy-hint">{t("clean.privacy")}</p>
      </Card>

      <Card className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("clean.stepOutput")}</h2>
            <p>{t("clean.stepOutputDescription")}</p>
          </div>
        </div>
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
              aria-describedby={`${outputNameId}-help`}
              onChange={(event) => {
                setOutputName(event.currentTarget.value);
                setError("");
                setSuccess(false);
              }}
            />
            <small>{t("clean.outputDescription")}</small>
          </span>
        </div>
        <p className="input-help" id={`${outputNameId}-help`}>
          {t("exportOptions.saveLocationHint")}
        </p>
        <p className="input-help">{t("clean.scopeWarning")}</p>
        {working ? <ExportProgress progress={exportProgress} /> : null}
        <Button type="submit" disabled={working || !file} className="action-button">
          {working ? <Spinner aria-label={t("common.loading")} /> : <Eraser size={18} />}
          {working ? t("clean.working") : t("clean.action")}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("clean.success", { fileName: outputName })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}
