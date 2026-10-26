import { useCallback, useEffect, useId, useState, type FormEvent } from "react";
import { ChevronDown, ChevronRight, FileArchive, FileText, SlidersHorizontal, Split, X } from "lucide-react";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useTranslation } from "react-i18next";

import { Button, Card, Input, Select, Spinner, Textarea } from "@internal/ui";
import { formatOperationError, processSplit } from "../../shared/api";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";
import { AdvancedSplit } from "./AdvancedSplit";
import { chunkRows, maxSplitGroups, parseSplitRanges, sourceBaseName, uniqueFileNames } from "./splitModel";
import "./split.css";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

/** Reads the page count of the selected PDF in the browser (no upload). */
function usePageCount(file: File | null) {
  const [pageCount, setPageCount] = useState(0);
  useEffect(() => {
    setPageCount(0);
    if (!file) return;
    let active = true;
    let task: ReturnType<typeof getDocument> | null = null;
    void file
      .arrayBuffer()
      .then((buffer) => {
        if (!active) return null;
        task = getDocument({ data: new Uint8Array(buffer) });
        return task.promise;
      })
      .then((documentProxy) => {
        if (!documentProxy) return;
        if (active) setPageCount(documentProxy.numPages);
        void documentProxy.destroy();
      })
      .catch(() => {
        if (active) setPageCount(0);
      });
    return () => {
      active = false;
      if (task) void task.destroy();
    };
  }, [file]);
  return pageCount;
}

export function SplitTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const chunkId = useId();
  const advancedId = useId();
  const modeId = useId();
  const rangesId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [fileKey, setFileKey] = useState(0);
  const [chunkSize, setChunkSize] = useState("1");
  const [simpleMode, setSimpleMode] = useState("chunks");
  const [rangesText, setRangesText] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const pageCount = usePageCount(file);

  const size = Number(chunkSize);
  const validSize = Number.isSafeInteger(size) && size >= 1;
  const customRanges = parseSplitRanges(rangesText, pageCount);
  const rangesInvalid = simpleMode === "ranges" && pageCount > 0 && rangesText.trim() !== "" && !customRanges;
  const documentCount = simpleMode === "ranges"
    ? customRanges?.length ?? 0
    : pageCount > 0 && validSize ? Math.ceil(pageCount / size) : 0;
  const folderName = file ? sourceBaseName(file.name) || "split" : "split";
  const canSubmit = Boolean(file) && documentCount > 0 && documentCount <= maxSplitGroups;

  const selectFile = useCallback((incoming: File | null) => {
    setFile(incoming);
    setFileKey((current) => current + 1);
    setError("");
    setSuccess(false);
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError(t("files.select"));
      return;
    }
    if (!canSubmit) {
      setError(t(simpleMode === "ranges" ? "split.rangesInvalid" : "split.simpleInvalid"));
      return;
    }
    const rows = simpleMode === "ranges"
      ? (customRanges ?? []).map((pages) => ({ pages }))
      : chunkRows(pageCount, size);
    const width = Math.max(2, String(rows.length).length);
    const names = uniqueFileNames(
      rows.map((_, index) => `${folderName}_${String(index + 1).padStart(width, "0")}`),
    );
    const data = new FormData();
    data.append("file", file, file.name);
    data.append("groups", JSON.stringify(rows.map((row, index) => ({ name: names[index], pages: row.pages }))));
    data.append("folder", folderName);
    setWorking(true);
    setError("");
    setSuccess(false);
    try {
      await processSplit(data, `${folderName}.zip`, t);
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
          ) : (
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
          )}
          <p className="input-help">{t("split.simpleHelp")}</p>
          <div className="output-preview">
            <span className="output-icon">
              <FileArchive size={21} aria-hidden="true" />
            </span>
            <span>
              <strong>{folderName}.zip</strong>
              <small>{t("split.outputSummary", { count: documentCount, folder: folderName })}</small>
            </span>
          </div>
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
                {t("split.success", { fileName: `${folderName}.zip`, count: documentCount })}
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
