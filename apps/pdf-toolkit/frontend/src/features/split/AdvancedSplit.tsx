import { useCallback, useId, useMemo, useState, type FormEvent } from "react";
import { FileArchive, Split } from "lucide-react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { useTranslation } from "react-i18next";

import { Button, Card, Input, Spinner } from "@internal/ui";
import {
  chooseSplitDestination,
  formatOperationError,
  processSplit,
  validateExportFileName,
  type ExportProgressState,
  type SplitDestination,
} from "../../shared/api";
import { SplitTable } from "./SplitTable";
import { SplitValuesPanel, type SplitMode, type ZoneSettings } from "./SplitValuesPanel";
import { ZonePreview } from "./ZonePreview";
import { ExportProgress } from "../shared/ExportProgress";
import {
  applyNamePattern,
  buildValuePattern,
  defaultNamePattern,
  defaultZone,
  fullPageZone,
  maxSplitGroups,
  parsePageSelection,
  sanitizeBaseName,
  sourceBaseName,
  uniqueFileNames,
  type SplitRow,
} from "./splitModel";
import { useZoneDetection } from "./useZoneDetection";
import "./split.css";

const defaultSettings: ZoneSettings = {
  scope: "zone",
  zone: defaultZone,
  valueType: "text",
  customPattern: "",
  grouping: "change",
  missing: "previous",
};

type AdvancedSplitProps = { file: File | null };

/** Value-based split (remount with a new `key` when the source file changes): table or automatic value detection, preview, naming pattern. */
export function AdvancedSplit({ file }: AdvancedSplitProps) {
  const { t } = useTranslation();
  const patternId = useId();
  const folderId = useId();
  const [pageCount, setPageCount] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [mode, setMode] = useState<SplitMode>("table");
  const zoneMode = mode === "zone";
  const [settings, setSettings] = useState<ZoneSettings>(defaultSettings);
  const [rows, setRows] = useState<SplitRow[]>([]);
  const [namePattern, setNamePattern] = useState(defaultNamePattern);
  const [folder, setFolder] = useState(() => (file ? sourceBaseName(file.name) : ""));
  const [documentProxy, setDocumentProxy] = useState<PDFDocumentProxy | null>(null);
  const [working, setWorking] = useState(false);
  const [exportProgress, setExportProgress] = useState<ExportProgressState>({
    phase: "uploading",
    percentage: 0,
  });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [successFileName, setSuccessFileName] = useState("");

  const valuePattern = useMemo(() => {
    try {
      return { pattern: buildValuePattern(settings.valueType, settings.customPattern), invalid: false };
    } catch {
      return { pattern: null, invalid: true };
    }
  }, [settings.valueType, settings.customPattern]);
  const patternError =
    settings.valueType === "regex" && (valuePattern.invalid || !settings.customPattern.trim());
  const detection = useZoneDetection({
    documentProxy,
    settings,
    pattern: valuePattern.pattern,
    patternError,
    t,
  });
  const { detecting, progress, feedback: detectFeedback } = detection;
  // In automatic mode, export re-runs the detection when the zone or settings changed since the last run.
  const needsDetection = zoneMode && detection.stale;

  const sourceName = file ? sourceBaseName(file.name) : "";
  const buildFileNames = useCallback(
    (list: SplitRow[]) =>
      uniqueFileNames(
        list.map((row, index) =>
          applyNamePattern(namePattern, {
            value: row.value.trim(),
            index: index + 1,
            pages: row.pages.trim(),
            sourceName,
            total: list.length,
          }),
        ),
      ),
    [namePattern, sourceName],
  );
  const fileNames = useMemo(() => buildFileNames(rows), [buildFileNames, rows]);
  const countInvalid = (list: SplitRow[]) =>
    pageCount > 0 ? list.filter((row) => parsePageSelection(row.pages, pageCount) === null).length : 0;
  const invalidRows = countInvalid(rows);
  const folderName = sanitizeBaseName(folder) || "split";
  const canSubmit = needsDetection
    ? Boolean(file) && !patternError
    : Boolean(file) && rows.length > 0 && rows.length <= maxSplitGroups && invalidRows === 0;

  const handlePageCount = useCallback((count: number) => {
    setPageCount(count);
    setPageNumber((current) => (count > 0 ? Math.min(current, count) : 1));
  }, []);

  const changeRows = (next: SplitRow[]) => {
    setRows(next);
    setSuccess(false);
  };

  const detect = async () => {
    if (!file) return null;
    setError("");
    setSuccess(false);
    const detected = await detection.detect();
    if (detected) setRows(detected);
    return detected;
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError(t("files.select"));
      return;
    }
    const archiveName = `${folderName}.zip`;
    const nameError = validateExportFileName(archiveName);
    if (nameError) {
      setError(t(`exportOptions.${nameError}`));
      return;
    }
    let destination: SplitDestination | null;
    try {
      destination = await chooseSplitDestination(archiveName, t);
    } catch (reason) {
      setError(formatOperationError(reason, t, "split.failed"));
      return;
    }
    if (destination === null) return;

    let target = rows;
    if (needsDetection) {
      const detected = await detect();
      if (!detected) return;
      target = detected;
    }
    const invalid = countInvalid(target);
    if (target.length === 0 || target.length > maxSplitGroups || invalid > 0) {
      setError(
        target.length === 0
          ? t("split.noRows")
          : invalid > 0
            ? t("split.invalidRows", { count: invalid })
            : t("split.tooManyRows", { max: maxSplitGroups }),
      );
      return;
    }
    const names = buildFileNames(target);
    setWorking(true);
    setExportProgress({ phase: "uploading", percentage: 0 });
    setError("");
    setSuccess(false);
    const data = new FormData();
    data.append("file", file, file.name);
    data.append(
      "groups",
      JSON.stringify(target.map((row, index) => ({ name: names[index], pages: row.pages.trim() }))),
    );
    data.append("folder", folderName);
    try {
      const savedName = await processSplit(
        data,
        archiveName,
        t,
        setExportProgress,
        destination,
      );
      setSuccessFileName(savedName);
      setSuccess(true);
    } catch (reason) {
      setError(formatOperationError(reason, t, "split.failed"));
    } finally {
      setWorking(false);
    }
  };

  const busy = working || detecting;

  return (
    <form className="split-workflow split-advanced-workflow" onSubmit={submit} noValidate>
      <div className="split-column">
        <Card className="panel">
          <div className="panel-heading">
            <span className="step-number">01</span>
            <div>
              <h2>{t("split.stepValues")}</h2>
              <p>{t("split.stepValuesDescription")}</p>
            </div>
          </div>
          <SplitValuesPanel
            mode={mode}
            settings={settings}
            pageCount={pageCount}
            disabled={busy || !file}
            detecting={detecting}
            progress={progress}
            patternError={patternError}
            onModeChange={setMode}
            onSettingsChange={setSettings}
            onDetect={() => void detect()}
            onAppendRows={(incoming) => changeRows([...rows, ...incoming])}
            onReplaceRows={changeRows}
          />
          {detectFeedback ? (
            <p
              className={`feedback ${
                detectFeedback.tone === "success"
                  ? "feedback-success"
                  : detectFeedback.tone === "warning"
                    ? "split-feedback-warning"
                    : "feedback-error"
              }`}
              role={detectFeedback.tone === "error" ? "alert" : "status"}
            >
              {detectFeedback.message}
            </p>
          ) : null}
        </Card>
      </div>

      <Card className="panel split-preview-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("split.stepPreview")}</h2>
            <p>
              {t(
                !zoneMode
                  ? "split.stepPreviewDescription"
                  : settings.scope === "page"
                    ? "split.stepPreviewPage"
                    : "split.stepPreviewZone",
              )}
            </p>
          </div>
        </div>
        {pageCount > 0 ? (
          <label className="split-page-select">
            <span>{t("split.pageLabel")}</span>
            <select
              value={pageNumber}
              disabled={busy}
              onChange={(event) => setPageNumber(Number(event.currentTarget.value))}
            >
              {Array.from({ length: pageCount }, (_, index) => index + 1).map((page) => (
                <option key={page} value={page}>
                  {t("split.pageOption", { page })}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <ZonePreview
          file={file}
          pageNumber={pageNumber}
          showZone={zoneMode}
          zoneEditable={settings.scope === "zone"}
          zone={settings.scope === "page" ? fullPageZone : settings.zone}
          valuePattern={valuePattern.pattern}
          disabled={busy}
          onPageCount={handlePageCount}
          onDocument={setDocumentProxy}
          onZoneChange={(zone) => setSettings((current) => ({ ...current, zone }))}
        />
      </Card>

      <Card className="panel split-output-panel">
        <div className="panel-heading">
          <span className="step-number">03</span>
          <div>
            <h2>{t("split.stepOutput")}</h2>
            <p>{t("split.stepOutputDescription")}</p>
          </div>
        </div>
        <div className="split-naming-grid">
          <div>
            <label className="field-label" htmlFor={patternId}>
              {t("split.patternLabel")}
            </label>
            <Input
              id={patternId}
              className="page-range-input"
              value={namePattern}
              disabled={busy}
              onChange={(event) => {
                setNamePattern(event.currentTarget.value);
                setSuccess(false);
              }}
            />
            <p className="input-help">{t("split.patternHelp")}</p>
          </div>
          <div>
            <label className="field-label" htmlFor={folderId}>
              {t("split.folderLabel")}
            </label>
            <Input
              id={folderId}
              value={folder}
              disabled={busy}
              placeholder="split"
              onChange={(event) => {
                setFolder(event.currentTarget.value);
                setSuccess(false);
              }}
            />
            <p className="input-help">{t("split.folderHelp")}</p>
          </div>
        </div>

        <SplitTable
          rows={rows}
          fileNames={fileNames}
          pageCount={pageCount}
          disabled={busy || !file}
          onRowsChange={changeRows}
        />
        {invalidRows > 0 ? (
          <p className="warning-note" role="alert">
            {t("split.invalidRows", { count: invalidRows })}
          </p>
        ) : null}
        {rows.length > maxSplitGroups ? (
          <p className="warning-note" role="alert">
            {t("split.tooManyRows", { max: maxSplitGroups })}
          </p>
        ) : null}

        <div className="output-preview">
          <span className="output-icon">
            <FileArchive size={21} aria-hidden="true" />
          </span>
          <span>
            <strong>{folderName}.zip</strong>
            <small>{t("split.outputSummary", { count: rows.length, folder: folderName })}</small>
          </span>
        </div>
        <p className="input-help">{t("exportOptions.saveLocationHint")}</p>
        {working ? <ExportProgress progress={exportProgress} /> : null}
        <Button type="submit" disabled={busy || !canSubmit} className="action-button">
          {working ? <Spinner aria-label={t("common.loading")} /> : <Split size={18} />}
          {working ? t("split.working") : t("split.action")}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("split.success", { fileName: successFileName, count: rows.length })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}
