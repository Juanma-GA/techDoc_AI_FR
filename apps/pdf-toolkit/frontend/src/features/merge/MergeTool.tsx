import { useState, type FormEvent } from "react";
import { ArrowDown, ArrowUp, Combine, FileText, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatOperationError, processPDF, type ExportProgressState } from "../../shared/api";
import { Button, Card, Spinner } from "@internal/ui";
import { ExportProgress } from "../shared/ExportProgress";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize, moveFileInList } from "../../shared/files";

export function MergeTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const [files, setFiles] = useState<File[]>([]);
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
    if (files.length < 2) {
      setError(t("merge.minimumFiles"));
      return;
    }

    setWorking(true);
    setExportProgress({ phase: "uploading", percentage: 0 });
    setError("");
    setSuccess(false);
    const data = new FormData();
    for (const file of files) {
      data.append("files", file, file.name);
    }
    try {
      await processPDF("merge", data, "merged.pdf", t, setExportProgress);
      setSuccess(true);
    } catch (reason) {
      setError(formatOperationError(reason, t, "errors.mergeFailed"));
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
            <h2>{t("merge.stepFiles")}</h2>
            <p>{t("merge.stepFilesDescription")}</p>
          </div>
        </div>
        <FileDropzone
          multiple
          disabled={working}
          onFiles={(incoming) => setFiles((current) => [...current, ...incoming])}
          onError={setError}
          label={t("files.dropMultipleLabel")}
          description={t("files.dropMultipleDescription")}
        />
        {files.length > 0 ? (
          <ol className="file-list" aria-label={t("merge.orderLabel")}>
            {files.map((file, index) => (
              <li className="file-row" key={`${file.name}-${file.lastModified}-${index}`}>
                <span className="file-order">{index + 1}</span>
                <span className="file-row-icon">
                  <FileText size={17} aria-hidden="true" />
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
                    aria-label={t("merge.moveUp", { name: file.name })}
                  >
                    <ArrowUp size={16} aria-hidden="true" />
                  </Button>
                  <Button
                    variant="ghost"
                    className="icon-button"
                    disabled={index === files.length - 1 || working}
                    onClick={() => moveFile(index, 1)}
                    aria-label={t("merge.moveDown", { name: file.name })}
                  >
                    <ArrowDown size={16} aria-hidden="true" />
                  </Button>
                  <Button
                    variant="ghost"
                    className="icon-button remove-button"
                    disabled={working}
                    onClick={() => setFiles((current) => current.filter((_, i) => i !== index))}
                    aria-label={t("merge.remove", { name: file.name })}
                  >
                    <X size={16} aria-hidden="true" />
                  </Button>
                </div>
              </li>
            ))}
          </ol>
        ) : null}
        <p className="privacy-hint">{t("merge.privacy")}</p>
      </Card>

      <Card className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("merge.stepOutput")}</h2>
            <p>{t("merge.stepOutputDescription")}</p>
          </div>
        </div>
        <div className="output-preview">
          <span className="output-icon">
            <FileText size={21} aria-hidden="true" />
          </span>
          <span>
            <strong>merged.pdf</strong>
            <small>{t("merge.outputDescription")}</small>
          </span>
        </div>
        {working ? <ExportProgress progress={exportProgress} /> : null}
        <Button type="submit" disabled={working || files.length < 2} className="action-button">
          {working ? <Spinner aria-label={t("common.loading")} /> : <Combine size={18} />}
          {working ? t("merge.working") : t("merge.action")}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("merge.success", { fileName: "merged.pdf" })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}
