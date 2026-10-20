import { useState, type FormEvent } from "react";
import { ArrowDown, ArrowUp, FileText, Image, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatOperationError, processPDF } from "../../shared/api";
import { Button, Card, Spinner } from "@internal/ui";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize, moveFileInList } from "../../shared/files";

export function ImagesToPdfTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);

  const moveFile = (index: number, offset: -1 | 1) => {
    setFiles((current) => moveFileInList(current, index, offset));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (files.length === 0) {
      setError(t("files.selectImagePdf"));
      return;
    }

    setWorking(true);
    setError("");
    setSuccess(false);
    const data = new FormData();
    for (const file of files) {
      data.append("images", file, file.name);
    }
    try {
      await processPDF("images-to-pdf", data, "images.pdf", t);
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
        <p className="privacy-hint">{t("imagesToPdf.privacy")}</p>
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
            <strong>images.pdf</strong>
            <small>{t("imagesToPdf.outputDescription")}</small>
          </span>
        </div>
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
              {t("imagesToPdf.success", { fileName: "images.pdf" })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}
