import { useId, useState, type FormEvent } from "react";
import { FilePlus2, FileText, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  chooseExportDestination,
  formatOperationError,
  processPDF,
  validateExportFileName,
  type ExportProgressState,
} from "../../shared/api";
import { Button, Card, Input, Select, Spinner } from "@internal/ui";
import { ExportProgress } from "../shared/ExportProgress";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";
import { resolveInsertAfter, resolveSourcePages, type InsertPosition } from "./insertModel";
import { usePdfPageCount } from "./usePdfPageCount";
import "./insert.css";

type FileSlotProps = {
  step: string;
  role: "target" | "source";
  file: File | null;
  pageCount: number;
  loading: boolean;
  failed: boolean;
  disabled: boolean;
  onFile: (file: File | null) => void;
  onError: (message: string) => void;
};

function FileSlot({ step, role, file, pageCount, loading, failed, disabled, onFile, onError }: FileSlotProps) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  return (
    <Card className="panel">
      <div className="panel-heading">
        <span className="step-number">{step}</span>
        <div>
          <h2>{t(`insert.${role}Heading`)}</h2>
          <p>{t(`insert.${role}Description`)}</p>
        </div>
      </div>
      <FileDropzone
        disabled={disabled}
        label={t(`insert.${role}Drop`)}
        onFiles={(incoming) => onFile(incoming[0] ?? null)}
        onError={onError}
      />
      {file ? (
        <div className="selected-file">
          <span className="file-row-icon">
            <FileText size={17} aria-hidden="true" />
          </span>
          <span className="file-details">
            <span className="file-name">{file.name}</span>
            <span className="file-size">
              {formatFileSize(file.size, language)}
              {" · "}
              {loading
                ? t("insert.countingPages")
                : failed
                  ? t("insert.documentFailed")
                  : t("insert.pageCount", { count: pageCount })}
            </span>
          </span>
          <Button
            variant="ghost"
            className="icon-button remove-button"
            disabled={disabled}
            onClick={() => onFile(null)}
            aria-label={t("files.remove")}
          >
            <X size={16} aria-hidden="true" />
          </Button>
        </div>
      ) : null}
    </Card>
  );
}

export function InsertTool() {
  const { t } = useTranslation();
  const pagesId = useId();
  const positionId = useId();
  const afterPageId = useId();
  const outputNameId = useId();
  const [target, setTarget] = useState<File | null>(null);
  const [source, setSource] = useState<File | null>(null);
  const [selection, setSelection] = useState("");
  const [position, setPosition] = useState<InsertPosition>("end");
  const [afterPage, setAfterPage] = useState("1");
  const [outputName, setOutputName] = useState("inserted.pdf");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);
  const [exportProgress, setExportProgress] = useState<ExportProgressState>({
    phase: "uploading",
    percentage: 0,
  });
  const targetDocument = usePdfPageCount(target);
  const sourceDocument = usePdfPageCount(source);
  const sourcePages = resolveSourcePages(selection, sourceDocument.pageCount);
  const after = resolveInsertAfter(position, afterPage, targetDocument.pageCount);
  const ready = Boolean(target && source) && !targetDocument.loading && !sourceDocument.loading;
  const selectionInvalid = ready && sourceDocument.pageCount > 0 && sourcePages === null;
  const afterInvalid = ready && targetDocument.pageCount > 0 && after === null;
  const canSubmit = ready && sourcePages !== null && after !== null && !working;

  const changed = () => {
    setError("");
    setSuccess(false);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!target || !source) {
      setError(t("insert.filesRequired"));
      return;
    }
    if (sourcePages === null || after === null) {
      setError(t(sourcePages === null ? "insert.invalidPages" : "insert.invalidPosition"));
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
    data.append("files", target, target.name);
    data.append("files", source, source.name);
    data.append("pages", selection.trim());
    data.append("after", String(after));
    try {
      const destination = await destinationChoice;
      if (destination === null) return;
      const savedName = await processPDF("insert", data, fileName, t, setExportProgress, destination);
      setOutputName(savedName);
      setSuccess(true);
    } catch (reason) {
      setError(formatOperationError(reason, t, "errors.pageOperationFailed"));
    } finally {
      setWorking(false);
    }
  };

  return (
    <form className="workflow-grid" onSubmit={submit}>
      <div className="insert-files">
        <FileSlot
          step="01"
          role="target"
          file={target}
          pageCount={targetDocument.pageCount}
          loading={targetDocument.loading}
          failed={targetDocument.failed}
          disabled={working}
          onFile={(file) => {
            setTarget(file);
            changed();
          }}
          onError={setError}
        />
        <FileSlot
          step="02"
          role="source"
          file={source}
          pageCount={sourceDocument.pageCount}
          loading={sourceDocument.loading}
          failed={sourceDocument.failed}
          disabled={working}
          onFile={(file) => {
            setSource(file);
            changed();
          }}
          onError={setError}
        />
      </div>

      <Card className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">03</span>
          <div>
            <h2>{t("insert.optionsHeading")}</h2>
            <p>{t("insert.optionsDescription")}</p>
          </div>
        </div>
        <label className="field-label" htmlFor={pagesId}>
          {t("insert.pagesLabel")}
        </label>
        <Input
          id={pagesId}
          className="page-range-input"
          type="text"
          autoComplete="off"
          spellCheck={false}
          placeholder={t("insert.pagesPlaceholder")}
          value={selection}
          disabled={working}
          aria-invalid={selectionInvalid}
          aria-describedby={`${pagesId}-help`}
          onChange={(event) => {
            setSelection(event.currentTarget.value);
            changed();
          }}
        />
        <p className="input-help" id={`${pagesId}-help`}>
          {selectionInvalid
            ? t("insert.invalidPages")
            : t("insert.pagesHelp", { count: sourceDocument.pageCount })}
        </p>
        <label className="field-label" htmlFor={positionId}>
          {t("insert.positionLabel")}
        </label>
        <Select
          id={positionId}
          value={position}
          disabled={working}
          options={[
            { value: "start", label: t("insert.positionStart") },
            { value: "after", label: t("insert.positionAfter") },
            { value: "end", label: t("insert.positionEnd") },
          ]}
          onChange={(event) => {
            setPosition(event.currentTarget.value as InsertPosition);
            changed();
          }}
        />
        {position === "after" ? (
          <>
            <label className="field-label" htmlFor={afterPageId}>
              {t("insert.afterPageLabel")}
            </label>
            <Input
              id={afterPageId}
              type="number"
              inputMode="numeric"
              min={1}
              max={targetDocument.pageCount || undefined}
              value={afterPage}
              disabled={working}
              aria-invalid={afterInvalid}
              aria-describedby={`${afterPageId}-help`}
              onChange={(event) => {
                setAfterPage(event.currentTarget.value);
                changed();
              }}
            />
            <p className="input-help" id={`${afterPageId}-help`}>
              {afterInvalid
                ? t("insert.invalidPosition")
                : t("insert.afterPageHelp", { count: targetDocument.pageCount })}
            </p>
          </>
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
                changed();
              }}
            />
            <small>
              {sourcePages !== null && after !== null
                ? t(after === 0 ? "insert.summaryStart" : "insert.summary", {
                    count: sourcePages.length,
                    after,
                  })
                : t("insert.outputDescription")}
            </small>
          </span>
        </div>
        <p className="input-help" id={`${outputNameId}-help`}>
          {t("exportOptions.saveLocationHint")}
        </p>
        {working ? <ExportProgress progress={exportProgress} /> : null}
        <Button type="submit" disabled={!canSubmit} className="action-button">
          {working ? <Spinner aria-label={t("common.loading")} /> : <FilePlus2 size={18} />}
          {working ? t("pages.working") : t("insert.action")}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("insert.success", { fileName: outputName })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}
