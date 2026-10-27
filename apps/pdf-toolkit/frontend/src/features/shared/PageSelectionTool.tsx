import { useId, useState, type FormEvent } from "react";
import { FileText, RotateCw, Scissors, Trash2, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  chooseExportDestination,
  formatOperationError,
  processPDF,
  validateExportFileName,
  type ExportProgressState,
} from "../../shared/api";
import { Button, Card, Input, Select, Spinner } from "@internal/ui";
import { ExportProgress } from "./ExportProgress";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";

type PageSelectionMode = "extract" | "delete" | "rotate";

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
  rotate: {
    endpoint: "rotate",
    outputName: "rotated.pdf",
    actionKey: "rotate.action",
    headingKey: "rotate.heading",
    descriptionKey: "rotate.description",
    outputKey: "rotate.outputDescription",
    icon: RotateCw,
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
  const rotationInputId = useId();
  const outputNameId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [selection, setSelection] = useState("");
  const [rotation, setRotation] = useState("90");
  const [outputName, setOutputName] = useState<string>(config.outputName);
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
    if (mode !== "rotate" && !selection.trim()) {
      setError(t("pages.selectPages"));
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
    data.append("pages", selection);
    if (mode === "rotate") {
      data.append("rotation", rotation);
    }
    try {
      const destination = await destinationChoice;
      if (destination === null) return;
      const savedName = await processPDF(
        config.endpoint,
        data,
        fileName,
        t,
        setExportProgress,
        destination,
      );
      setOutputName(savedName);
      setSuccess(true);
    } catch (reason) {
      setError(
        formatOperationError(
          reason,
          t,
          mode === "rotate" ? "errors.rotationFailed" : "errors.pageOperationFailed",
        ),
      );
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
      </Card>

      <Card className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t(config.headingKey)}</h2>
            <p>{t(config.descriptionKey)}</p>
          </div>
        </div>
        <label className="field-label" htmlFor={pageInputId}>
          {t(mode === "rotate" ? "rotate.pagesFieldLabel" : "pages.fieldLabel")}
        </label>
        <Input
          id={pageInputId}
          className="page-range-input"
          type="text"
          autoComplete="off"
          spellCheck={false}
          placeholder={t(mode === "rotate" ? "rotate.pagesPlaceholder" : "pages.placeholder")}
          value={selection}
          disabled={working}
          onChange={(event) => {
            setSelection(event.currentTarget.value);
            setSuccess(false);
          }}
          aria-describedby={`${pageInputId}-help`}
        />
        <p className="input-help" id={`${pageInputId}-help`}>
          {t(mode === "rotate" ? "rotate.pagesHelp" : "pages.help")}
        </p>
        {mode === "rotate" ? (
          <>
            <label className="field-label" htmlFor={rotationInputId}>
              {t("rotate.angleLabel")}
            </label>
            <Select
              id={rotationInputId}
              options={[
                { value: "90", label: t("rotate.clockwise90") },
                { value: "180", label: t("rotate.clockwise180") },
                { value: "270", label: t("rotate.clockwise270") },
              ]}
              value={rotation}
              disabled={working}
              onChange={(event) => {
                setRotation(event.currentTarget.value);
                setSuccess(false);
              }}
            />
          </>
        ) : null}
        {mode === "delete" ? (
          <p className="warning-note">{t("pages.deleteWarning")}</p>
        ) : null}
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
            <small>{t(config.outputKey)}</small>
          </span>
        </div>
        <p className="input-help" id={`${outputNameId}-help`}>
          {t("exportOptions.saveLocationHint")}
        </p>
        {working ? <ExportProgress progress={exportProgress} /> : null}
        <Button
          type="submit"
          disabled={working || !file || (mode !== "rotate" && !selection.trim())}
          className="action-button"
        >
          {working ? <Spinner aria-label={t("common.loading")} /> : <Icon size={18} />}
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
              {t(mode === "rotate" ? "rotate.success" : "pages.success", { fileName: outputName })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}
