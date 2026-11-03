import { useId, useState, type FormEvent } from "react";
import { ArrowDown, ArrowUp, FileText, Image, X } from "lucide-react";
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
import { formatFileSize, moveFileInList } from "../../shared/files";

export function ImagesToPdfTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const outputNameId = useId();
  const [files, setFiles] = useState<File[]>([]);
  const [outputName, setOutputName] = useState("images.pdf");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);
  const [exportProgress, setExportProgress] = useState<ExportProgressState>({
    phase: "uploading",
    percentage: 0,
  });

  const moveFile = (index: number, offset: -1 | 1) => {
    setFiles((current) => moveFileInList(current, index, offset));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (files.length === 0) {
      setError(t("files.selectImagePdf"));
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
    for (const file of files) {
      data.append("images", file, file.name);
    }
    try {
      const destination = await destinationChoice;
      if (destination === null) return;
      const savedName = await processPDF(
        "images-to-pdf",
        data,
        fileName,
        t,
        setExportProgress,
        destination,
      );
      setOutputName(savedName);
      setSuccess(true);
    } catch (reason) {
      setError(formatOperationError(reason, t, "errors.imagesToPdfFailed"));
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
            <h2>{t("imagesToPdf.stepFiles")}</h2>
            <p>{t("imagesToPdf.stepFilesDescription")}</p>
          </div>
        </div>
        <FileDropzone
          fileType="image"
          multiple
          disabled={working}
          onFiles={(incoming) => {
            setFiles((current) => [...current, ...incoming]);
            setError("");
            setSuccess(false);
          }}
          onError={setError}
          label={t("files.imageDropLabel")}
          description={t("files.imageDropDescription")}
        />
        {files.length > 0 ? (
          <ol className="file-list" aria-label={t("imagesToPdf.orderLabel")}>
            {files.map((file, index) => (
              <li className="file-row" key={`${file.name}-${file.lastModified}-${index}`}>
                <span className="file-order">{index + 1}</span>
                <span className="file-row-icon">
                  <Image size={17} aria-hidden="true" />
                </span>
                <span className="file-details">
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">{formatFileSize(file.size, language)}</span>
                </span>
                <div className="file-actions">
                  <Button
                    variant="ghost"
                    className="icon-button"
                    disabled={index === 0 || working}
                    onClick={() => moveFile(index, -1)}
                    aria-label={t("imagesToPdf.moveUp", { name: file.name })}
                  >
                    <ArrowUp size={16} aria-hidden="true" />
                  </Button>
                  <Button
                    variant="ghost"
                    className="icon-button"
                    disabled={index === files.length - 1 || working}
                    onClick={() => moveFile(index, 1)}
                    aria-label={t("imagesToPdf.moveDown", { name: file.name })}
                  >
                    <ArrowDown size={16} aria-hidden="true" />
                  </Button>
                  <Button
                    variant="ghost"
                    className="icon-button remove-button"
                    disabled={working}
                    onClick={() => {
                      setFiles((current) => current.filter((_, fileIndex) => fileIndex !== index));
                      setSuccess(false);
                    }}
                    aria-label={t("imagesToPdf.remove", { name: file.name })}
                  >
                    <X size={16} aria-hidden="true" />
                  </Button>
                </div>
              </li>
            ))}
          </ol>
        ) : null}
      </Card>

      <Card className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("imagesToPdf.stepOutput")}</h2>
            <p>{t("imagesToPdf.stepOutputDescription")}</p>
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
            <small>{t("imagesToPdf.outputDescription")}</small>
          </span>
        </div>
        <p className="input-help" id={`${outputNameId}-help`}>
          {t("exportOptions.saveLocationHint")}
        </p>
        {working ? <ExportProgress progress={exportProgress} /> : null}
        <Button type="submit" disabled={working || files.length === 0} className="action-button">
          {working ? <Spinner aria-label={t("common.loading")} /> : <FileText size={18} />}
          {working ? t("imagesToPdf.working") : t("imagesToPdf.action")}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("imagesToPdf.success", { fileName: outputName })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}
