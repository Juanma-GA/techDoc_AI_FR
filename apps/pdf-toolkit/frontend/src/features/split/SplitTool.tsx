import { useCallback, useId, useState, type FormEvent } from "react";
import { ChevronDown, ChevronRight, FileArchive, FileText, SlidersHorizontal, Split, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button, Card, Input, Select, Spinner, Textarea } from "@internal/ui";
import {
  chooseSplitDestination,
  formatOperationError,
  processSplit,
  validateExportFileName,
  type ExportProgressState,
} from "../../shared/api";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";
import { ExportProgress } from "../shared/ExportProgress";
import { AdvancedSplit } from "./AdvancedSplit";
import { bookmarkGroups } from "./bookmarkSplit";
import { useSplitDocument } from "./useSplitDocument";
import {
  chunkRows,
  maxSplitGroups,
  parseSplitRanges,
  sanitizeBaseName,
  sourceBaseName,
  uniqueFileNames,
} from "./splitModel";
import "./split.css";

export function SplitTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const chunkId = useId();
  const advancedId = useId();
  const modeId = useId();
  const rangesId = useId();
  const folderId = useId();
  const bookmarkLevelId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [fileKey, setFileKey] = useState(0);
  const [folder, setFolder] = useState("split");
  const [chunkSize, setChunkSize] = useState("1");
  const [simpleMode, setSimpleMode] = useState("chunks");
  const [bookmarkLevel, setBookmarkLevel] = useState(1);
  const [rangesText, setRangesText] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [working, setWorking] = useState(false);
  const [exportProgress, setExportProgress] = useState<ExportProgressState>({
    phase: "uploading",
    percentage: 0,
  });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [successFileName, setSuccessFileName] = useState("");
  const document = useSplitDocument(file);
  const { pageCount } = document;
  const levels = [...new Set(document.bookmarks.map((bookmark) => bookmark.level))].sort((a, b) => a - b);
  const selectedBookmarkLevel = levels.includes(bookmarkLevel) ? bookmarkLevel : levels[0] ?? 1;
  const bookmarkRows = bookmarkGroups(document.bookmarks, selectedBookmarkLevel, pageCount);

  const size = Number(chunkSize);
  const validSize = Number.isSafeInteger(size) && size >= 1;
  const customRanges = parseSplitRanges(rangesText, pageCount);
  const rangesInvalid = simpleMode === "ranges" && pageCount > 0 && rangesText.trim() !== "" && !customRanges;
  const documentCount = simpleMode === "bookmarks" ? bookmarkRows.length : simpleMode === "ranges"
    ? customRanges?.length ?? 0
    : pageCount > 0 && validSize ? Math.ceil(pageCount / size) : 0;
  const folderName = sanitizeBaseName(folder) || "split";
  const archiveName = `${folderName}.zip`;
  const canSubmit = Boolean(file) && !document.loading &&
    !(simpleMode === "bookmarks" && document.error) &&
    documentCount > 0 && documentCount <= maxSplitGroups;

  const selectFile = useCallback((incoming: File | null) => {
    setFile(incoming);
    setFileKey((current) => current + 1);
    setFolder(incoming ? sourceBaseName(incoming.name) || "split" : "split");
    setError("");
    setSuccess(false);
    setBookmarkLevel(1);
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError(t("files.select"));
      return;
    }
    if (!canSubmit) {
      setError(t(simpleMode === "bookmarks" ? "split.bookmarksEmpty" :
        simpleMode === "ranges" ? "split.rangesInvalid" : "split.simpleInvalid"));
      return;
    }
    const nameError = validateExportFileName(archiveName);
    if (nameError) {
      setError(t(`exportOptions.${nameError}`));
      return;
    }
    const destinationChoice = chooseSplitDestination(archiveName, t);
    const rows = simpleMode === "bookmarks" ? bookmarkRows : simpleMode === "ranges"
      ? (customRanges ?? []).map((pages) => ({ pages }))
      : chunkRows(pageCount, size);
    const width = Math.max(2, String(rows.length).length);
    const names = uniqueFileNames(
      rows.map((row, index) => simpleMode === "bookmarks" && "title" in row &&
        typeof row.title === "string" && row.title.trim()
        ? row.title
        : `${folderName}_${String(index + 1).padStart(width, "0")}`),
    );
    const data = new FormData();
    data.append("file", file, file.name);
    data.append("groups", JSON.stringify(rows.map((row, index) => ({ name: names[index], pages: row.pages }))));
    data.append("folder", folderName);
    setWorking(true);
    setExportProgress({ phase: "uploading", percentage: 0 });
    setError("");
    setSuccess(false);
    try {
      const destination = await destinationChoice;
      if (destination === null) return;
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

  return (
    <div className="split-tool">
      <form className="split-workflow" onSubmit={submit} noValidate>
        <Card className="panel">
          <div className="panel-heading">
            <span className="step-number">01</span>
            <div>
              <h2>{t("split.stepFile")}</h2>
              <p>{t("split.stepFileDescription")}</p>
            </div>
          </div>
          <FileDropzone disabled={working} onFiles={(incoming) => selectFile(incoming[0] ?? null)} onError={setError} />
          {file ? (
            <div className="selected-file">
              <span className="file-row-icon">
                <FileText size={17} aria-hidden="true" />
              </span>
              <span className="file-details">
                <span className="file-name">{file.name}</span>
                <span className="file-size">
                  {formatFileSize(file.size, language)}
                  {pageCount > 0 ? ` - ${t("split.pageCount", { count: pageCount })}` : ""}
                </span>
              </span>
              <Button
                variant="ghost"
                className="icon-button remove-button"
                disabled={working}
                onClick={() => selectFile(null)}
                aria-label={t("files.remove")}
              >
                <X size={16} aria-hidden="true" />
              </Button>
            </div>
          ) : null}
          <p className="privacy-hint">{t("split.privacy")}</p>
          {document.error === "split.documentFailed" ? (
            <p className="feedback feedback-error" role="alert">{t(document.error)}</p>
          ) : null}
        </Card>

        <Card className="panel">
          <div className="panel-heading">
            <span className="step-number">02</span>
            <div>
              <h2>{t("split.simpleTitle")}</h2>
              <p>{t("split.simpleDescription")}</p>
            </div>
          </div>
          <label className="field-label" htmlFor={modeId}>{t("split.simpleMode")}</label>
          <Select
            id={modeId}
            value={simpleMode}
            disabled={working}
            options={[
              { value: "chunks", label: t("split.chunkLabel") },
              { value: "ranges", label: t("split.rangesLabel") },
              { value: "bookmarks", label: t("split.bookmarksMode") },
            ]}
            onChange={(event) => {
              setSimpleMode(event.currentTarget.value);
              setError("");
              setSuccess(false);
            }}
          />
          {simpleMode === "chunks" ? (
            <>
          <label className="field-label" htmlFor={chunkId}>
            {t("split.chunkLabel")}
          </label>
          <Input
            id={chunkId}
            className="split-chunk-input"
            type="number"
            min={1}
            value={chunkSize}
            disabled={working || !file}
            onChange={(event) => {
              setChunkSize(event.currentTarget.value);
              setSuccess(false);
            }}
          />
            </>
          ) : simpleMode === "ranges" ? (
            <>
              <label className="field-label" htmlFor={rangesId}>{t("split.rangesLabel")}</label>
              <Textarea
                id={rangesId}
                rows={3}
                value={rangesText}
                disabled={working || !file}
                placeholder="1-4 ; 5-8 ; 9-12 ; 13-16"
                aria-invalid={rangesInvalid}
                aria-describedby={`${rangesId}-help`}
                onChange={(event) => {
                  setRangesText(event.currentTarget.value);
                  setError("");
                  setSuccess(false);
                }}
              />
              <p id={`${rangesId}-help`} className="input-help">{t("split.rangesHelp")}</p>
              {rangesInvalid ? <p className="warning-note" role="alert">{t("split.rangesInvalid")}</p> : null}
            </>
          ) : (
            <>
              <label className="field-label" htmlFor={bookmarkLevelId}>{t("split.bookmarkLevel")}</label>
              <Select
                id={bookmarkLevelId}
                value={String(selectedBookmarkLevel)}
                disabled={working || document.loading || levels.length === 0}
                aria-describedby={`${bookmarkLevelId}-help`}
                options={levels.map((level) => ({
                  value: String(level), label: t("split.bookmarkLevelOption", { level }),
                }))}
                onChange={(event) => {
                  setBookmarkLevel(Number(event.currentTarget.value));
                  setError("");
                  setSuccess(false);
                }}
              />
              <p className="input-help" id={`${bookmarkLevelId}-help`}>{t("split.bookmarksHelp")}</p>
              {document.loading ? <p role="status">{t("split.bookmarksLoading")}</p> : null}
              {document.error === "split.bookmarksFailed" ? (
                <p className="feedback feedback-error" role="alert">{t(document.error)}</p>
              ) : file && !document.loading && !document.error && levels.length === 0 ? (
                <p className="warning-note" role="status">{t("split.bookmarksEmpty")}</p>
              ) : null}
              {document.skipped > 0 ? (
                <p className="warning-note" role="status">{t("split.bookmarksSkipped", { count: document.skipped })}</p>
              ) : null}
              {documentCount > maxSplitGroups ? (
                <p className="warning-note" role="alert">{t("split.tooManyRows", { max: maxSplitGroups })}</p>
              ) : null}
            </>
          )}
          <p className="input-help">{t(simpleMode === "bookmarks" ? "split.bookmarksNames" : "split.simpleHelp")}</p>
          <label className="field-label" htmlFor={folderId}>
            {t("split.folderLabel")}
          </label>
          <Input
            id={folderId}
            value={folder}
            disabled={working}
            aria-describedby={`${folderId}-help`}
            onChange={(event) => {
              setFolder(event.currentTarget.value);
              setError("");
              setSuccess(false);
            }}
          />
          <p className="input-help" id={`${folderId}-help`}>
            {t("split.simpleFolderHelp")}
          </p>
          <div className="output-preview">
            <span className="output-icon">
              <FileArchive size={21} aria-hidden="true" />
            </span>
            <span>
              <strong>{archiveName}</strong>
              <small>{t("split.outputSummary", { count: documentCount, folder: folderName })}</small>
            </span>
          </div>
          <p className="input-help">{t("exportOptions.saveLocationHint")}</p>
          {working ? <ExportProgress progress={exportProgress} /> : null}
          <Button type="submit" disabled={working || !canSubmit} className="action-button">
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
                {t("split.success", { fileName: successFileName, count: documentCount })}
              </p>
            ) : null}
          </div>
        </Card>
      </form>

      <Card className="panel split-advanced-panel">
        <Button
          variant="ghost"
          aria-expanded={advanced}
          aria-controls={advancedId}
          onClick={() => setAdvanced((current) => !current)}
        >
          {advanced ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}
          <SlidersHorizontal size={16} aria-hidden="true" />
          {t("split.advancedToggle")}
        </Button>
        <p className="input-help">{t("split.advancedHint")}</p>
        {advanced ? (
          <div id={advancedId} className="split-advanced-body">
            {file ? (
              <AdvancedSplit key={fileKey} file={file} />
            ) : (
              <p className="input-help">{t("split.advancedNeedsFile")}</p>
            )}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
