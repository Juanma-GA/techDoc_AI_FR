import { useId, useState, type FormEvent } from "react";
import { FilePenLine, FileText, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, Card, Input, Spinner } from "@internal/ui";

import {
  chooseExportDestination,
  formatOperationError,
  processPDF,
  validateExportFileName,
  type ExportProgressState,
} from "../../shared/api";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";
import { ExportProgress } from "../shared/ExportProgress";
import { usePdfMetadata } from "./usePdfMetadata";

const fields = ["title", "author", "subject", "keywords"] as const;

export function MetadataTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const id = useId();
  const [file, setFile] = useState<File | null>(null);
  const metadata = usePdfMetadata(file);
  const [outputName, setOutputName] = useState("metadata.pdf");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);
  const [progress, setProgress] = useState<ExportProgressState>({
    phase: "uploading", percentage: 0,
  });
  const ready = Boolean(file) && !metadata.loading && !metadata.failed;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || !ready) {
      setError(t(metadata.failed ? "metadata.readFailed" : "files.select"));
      return;
    }
    const filename = outputName.trim();
    const nameError = validateExportFileName(filename);
    if (nameError) {
      setError(t(`exportOptions.${nameError}`));
      return;
    }
    const destinationChoice = chooseExportDestination(filename, t);
    setWorking(true);
    setError("");
    setSuccess(false);
    setProgress({ phase: "uploading", percentage: 0 });
    try {
      const destination = await destinationChoice;
      if (destination === null) return;
      const data = new FormData();
      data.append("file", file, file.name);
      for (const field of fields) data.append(field, metadata.values[field]);
      const savedName = await processPDF(
        "edit-metadata", data, filename, t, setProgress, destination,
      );
      setOutputName(savedName);
      setSuccess(true);
    } catch (reason: unknown) {
      setError(formatOperationError(reason, t, "errors.metadataFailed"));
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
            <h2>{t("metadata.stepFile")}</h2>
            <p>{t("metadata.stepFileDescription")}</p>
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
            <span className="file-row-icon"><FileText size={17} aria-hidden="true" /></span>
            <span className="file-details">
              <span className="file-name">{file.name}</span>
              <span className="file-size">{formatFileSize(file.size, language)}</span>
            </span>
            <Button
              variant="ghost"
              className="icon-button remove-button"
              disabled={working}
              aria-label={t("files.remove")}
              onClick={() => {
                setFile(null);
                setError("");
                setSuccess(false);
              }}
            >
              <X size={16} aria-hidden="true" />
            </Button>
          </div>
        ) : null}
        {metadata.loading ? (
          <p className="preview-status" role="status">
            <Spinner aria-label={t("common.loading")} />{t("metadata.reading")}
          </p>
        ) : null}
        {metadata.failed ? (
          <p className="feedback feedback-error" role="alert">{t("metadata.readFailed")}</p>
        ) : null}
      </Card>

      <Card className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("metadata.stepProperties")}</h2>
            <p id={`${id}-fields-help`}>{t("metadata.fieldsHelp")}</p>
          </div>
        </div>
        <div className="grid gap-3">
          {fields.map((field) => (
            <div key={field}>
              <label className="field-label" htmlFor={`${id}-${field}`}>
                {t(`metadata.${field}`)}
              </label>
              <Input
                id={`${id}-${field}`}
                value={metadata.values[field]}
                disabled={working || !ready}
                aria-describedby={`${id}-fields-help`}
                onChange={(event) => {
                  metadata.update(field, event.currentTarget.value);
                  setError("");
                  setSuccess(false);
                }}
              />
            </div>
          ))}
        </div>
        <div className="output-preview">
          <span className="output-icon"><FileText size={21} aria-hidden="true" /></span>
          <span>
            <label className="field-label" htmlFor={`${id}-output`}>
              {t("exportOptions.fileName")}
            </label>
            <Input
              id={`${id}-output`}
              value={outputName}
              disabled={working}
              aria-describedby={`${id}-output-help`}
              onChange={(event) => {
                setOutputName(event.currentTarget.value);
                setError("");
                setSuccess(false);
              }}
            />
          </span>
        </div>
        <p className="input-help" id={`${id}-output-help`}>{t("exportOptions.saveLocationHint")}</p>
        <p className="input-help">{t("metadata.warning")}</p>
        {working ? <ExportProgress progress={progress} /> : null}
        <Button type="submit" disabled={working || !ready} className="action-button">
          {working ? <Spinner aria-label={t("common.loading")} /> : <FilePenLine size={18} />}
          {t(working ? "metadata.working" : "metadata.action")}
        </Button>
        <div className="feedback-slot">
          {error ? <p className="feedback feedback-error" role="alert">{error}</p> : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("metadata.success", { fileName: outputName })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}
