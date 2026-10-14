import { useId, useState, type FormEvent } from "react";
import { FileText, Scissors, Trash2, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { formatOperationError, processPDF } from "../../shared/api";
import { Button } from "../../shared/components/Button";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";

type PageSelectionMode = "extract" | "delete";

const modeConfiguration = {
  extract: {
    endpoint: "extract",
    outputName: "extract.pdf",
    actionKey: "pages.extractAction",
    headingKey: "pages.extractHeading",
    descriptionKey: "pages.extractDescription",
    outputKey: "pages.extractOutput",
    icon: Scissors,
  },
  delete: {
    endpoint: "delete",
    outputName: "trimmed.pdf",
    actionKey: "pages.deleteAction",
    headingKey: "pages.deleteHeading",
    descriptionKey: "pages.deleteDescription",
    outputKey: "pages.deleteOutput",
    icon: Trash2,
  },
} as const;

type PageSelectionToolProps = {
  mode: PageSelectionMode;
};

export function PageSelectionTool({ mode }: PageSelectionToolProps) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const config = modeConfiguration[mode];
  const Icon = config.icon;
  const pageInputId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [selection, setSelection] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError(t("files.select"));
      return;
    }
    if (!selection.trim()) {
      setError(t("pages.selectPages"));
      return;
    }

    setWorking(true);
    setError("");
    setSuccess(false);
    const data = new FormData();
    data.append("file", file, file.name);
    data.append("pages", selection);
    try {
      await processPDF(config.endpoint, data, config.outputName, t);
      setSuccess(true);
    } catch (reason) {
      setError(formatOperationError(reason, t, "errors.pageOperationFailed"));
    } finally {
      setWorking(false);
    }
  };

  return (
    <form className="workflow-grid" onSubmit={submit}>
      <section className="panel">
        <div className="panel-heading">
          <span className="step-number">01</span>
          <div>
            <h2>{t("pages.stepFile")}</h2>
            <p>{t("pages.stepFileDescription")}</p>
          </div>
        </div>
        <FileDropzone
          disabled={working}
          onFiles={(incoming) => {
            setFile(incoming[0] ?? null);
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
                setSelection("");
              }}
              aria-label={t("files.remove")}
            >
              <X size={16} aria-hidden="true" />
            </Button>
          </div>
        ) : null}
        <p className="privacy-hint">{t("pages.privacy")}</p>
      </section>

      <section className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t(config.headingKey)}</h2>
            <p>{t(config.descriptionKey)}</p>
          </div>
        </div>
        <label className="field-label" htmlFor={pageInputId}>{t("pages.fieldLabel")}</label>
        <input
          id={pageInputId}
          className="text-input page-range-input"
          type="text"
          autoComplete="off"
          spellCheck={false}
          placeholder={t("pages.placeholder")}
          value={selection}
          disabled={working}
          onChange={(event) => {
            setSelection(event.currentTarget.value);
            setSuccess(false);
          }}
          aria-describedby={`${pageInputId}-help`}
        />
        <p className="input-help" id={`${pageInputId}-help`}>
          {t("pages.help")}
        </p>
        {mode === "delete" ? (
          <p className="warning-note">{t("pages.deleteWarning")}</p>
        ) : null}
        <div className="output-preview">
          <span className="output-icon">
            <FileText size={21} aria-hidden="true" />
          </span>
          <span>
            <strong>{config.outputName}</strong>
            <small>{t(config.outputKey)}</small>
          </span>
        </div>
        <Button
          type="submit"
          disabled={working || !file || !selection.trim()}
          className="action-button"
        >
          {working ? <span className="spinner" aria-hidden="true" /> : <Icon size={18} />}
          {working ? t("pages.working") : t(config.actionKey)}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("pages.success", { fileName: config.outputName })}
            </p>
          ) : null}
        </div>
      </section>
    </form>
  );
}
