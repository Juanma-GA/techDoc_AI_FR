import { useState, type FormEvent } from "react";
import { FileText, Minimize2, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatOperationError, processPDF } from "../../shared/api";
import { Button, Card, Spinner } from "@internal/ui";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";

export function CompressTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError(t("files.select"));
      return;
    }

    setWorking(true);
    setError("");
    setSuccess(false);
    const data = new FormData();
    data.append("file", file, file.name);
    try {
      await processPDF("compress", data, "compressed.pdf", t);
      setSuccess(true);
    } catch (reason) {
      setError(formatOperationError(reason, t, "errors.compressionFailed"));
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
            <h2>{t("compress.stepFile")}</h2>
            <p>{t("compress.stepFileDescription")}</p>
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
        <p className="privacy-hint">{t("compress.privacy")}</p>
      </Card>

      <Card className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("compress.stepOutput")}</h2>
            <p>{t("compress.stepOutputDescription")}</p>
          </div>
        </div>
        <div className="output-preview">
          <span className="output-icon">
            <FileText size={21} aria-hidden="true" />
          </span>
          <span>
            <strong>compressed.pdf</strong>
            <small>{t("compress.outputDescription")}</small>
          </span>
        </div>
        <Button type="submit" disabled={working || !file} className="action-button">
          {working ? <Spinner aria-label={t("common.loading")} /> : <Minimize2 size={18} />}
          {working ? t("compress.working") : t("compress.action")}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("compress.success", { fileName: "compressed.pdf" })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}
