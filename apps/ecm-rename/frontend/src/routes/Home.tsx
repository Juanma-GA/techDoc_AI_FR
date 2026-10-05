import { useMutation } from "@tanstack/react-query";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Select } from "@internal/ui";
import { FileSearch, FolderPlus, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ecmRenameApi,
  type PreviewDto,
  type PreviewRequest,
  type ProcessDto,
  type TrackerField,
} from "../lib/api";

type FolderField = Extract<TrackerField, "reference" | "revision" | "subject">;

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "object" && error !== null && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return fallback;
}

function folderName(record: PreviewDto["records"][number]): string {
  return [record.reference, record.revision, record.subject]
    .map((part) => part.trim())
    .filter(Boolean)
    .join("-");
}

export function Home({ onProcessed }: { onProcessed: (result: ProcessDto) => void }) {
  const { t } = useTranslation();
  const [sourcePath, setSourcePath] = useState("");
  const [trackerPath, setTrackerPath] = useState("");
  const [outputPath, setOutputPath] = useState("");
  const [sheetName, setSheetName] = useState("");
  const [headerRow, setHeaderRow] = useState("");
  const [preview, setPreview] = useState<PreviewDto | null>(null);
  const [confirmationArmed, setConfirmationArmed] = useState(false);

  const previewMutation = useMutation({
    mutationFn: ecmRenameApi.preview,
    onSuccess: (result) => {
      setPreview(result);
      setSheetName(result.sheet_name);
      setHeaderRow(String(result.header_row));
      processMutation.reset();
      setConfirmationArmed(false);
    },
  });

  const processMutation = useMutation({
    mutationFn: ecmRenameApi.process,
    onSuccess: onProcessed,
  });

  useEffect(() => {
    if (!confirmationArmed) return;
    const timeout = window.setTimeout(() => setConfirmationArmed(false), 3000);
    return () => window.clearTimeout(timeout);
  }, [confirmationArmed]);

  const layoutDirty = Boolean(
    preview && (preview.sheet_name !== sheetName || preview.header_row !== Number(headerRow)),
  );
  const readyToProcess = Boolean(
    preview &&
      outputPath.trim() &&
      !layoutDirty &&
      preview.records.length > 0 &&
      preview.records.every((record) => record.reference.trim() && record.subject.trim()),
  );

  function clearPreview() {
    setPreview(null);
    setSheetName("");
    setHeaderRow("");
    previewMutation.reset();
    processMutation.reset();
    setConfirmationArmed(false);
  }

  function analyze() {
    const request: PreviewRequest = {
      source_path: sourcePath.trim(),
      tracker_path: trackerPath.trim(),
    };
    if (sheetName) request.sheet_name = sheetName;
    if (preview && headerRow) request.header_row = Number(headerRow);
    previewMutation.mutate(request);
  }

  function updateFolderField(recordIndex: number, field: FolderField, value: string) {
    setConfirmationArmed(false);
    setPreview((current) => {
      if (!current) return current;
      return {
        ...current,
        records: current.records.map((record, index) => {
          if (index !== recordIndex) return record;
          const trackerValues = [...record.tracker_values];
          current.columns.forEach((column, columnIndex) => {
            if (column.field === field) trackerValues[columnIndex] = value;
          });
          return { ...record, [field]: value, tracker_values: trackerValues };
        }),
      };
    });
  }

  function updateTrackerValue(recordIndex: number, columnIndex: number, value: string) {
    setConfirmationArmed(false);
    setPreview((current) => {
      if (!current) return current;
      return {
        ...current,
        records: current.records.map((record, index) => {
          if (index !== recordIndex) return record;
          const trackerValues = [...record.tracker_values];
          trackerValues[columnIndex] = value;
          const field = current.columns[columnIndex]?.field;
          if (field === "reference" || field === "revision" || field === "subject") {
            return { ...record, [field]: value, tracker_values: trackerValues };
          }
          return { ...record, tracker_values: trackerValues };
        }),
      };
    });
  }

  function confirmProcess() {
    if (!preview || !readyToProcess) return;
    if (!confirmationArmed) {
      setConfirmationArmed(true);
      return;
    }
    setConfirmationArmed(false);
    processMutation.mutate({
      source_path: preview.source_path,
      tracker_path: preview.tracker_path,
      output_path: outputPath.trim(),
      sheet_name: preview.sheet_name,
      header_row: preview.header_row,
      records: preview.records.map(({ source_path, reference, revision, subject, tracker_values }) => ({
        source_path,
        reference,
        revision,
        subject,
        tracker_values,
      })),
    });
  }

  return (
    <div>
      <header className="page-header">
        <div>
          <h1>{t("home.title")}</h1>
          <p>{t("home.subtitle")}</p>
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>{t("home.inputs_title")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1">
              <span className="label">{t("home.source")}</span>
              <Input
                autoComplete="off"
                spellCheck={false}
                disabled={previewMutation.isPending || processMutation.isPending}
                value={sourcePath}
                placeholder={t("home.source_placeholder")}
                onChange={(event) => {
                  setSourcePath(event.currentTarget.value);
                  clearPreview();
                }}
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="label">{t("home.tracker")}</span>
              <Input
                autoComplete="off"
                spellCheck={false}
                disabled={previewMutation.isPending || processMutation.isPending}
                value={trackerPath}
                placeholder={t("home.tracker_placeholder")}
                onChange={(event) => {
                  setTrackerPath(event.currentTarget.value);
                  clearPreview();
                }}
              />
            </label>
            <label className="flex flex-col gap-1 md:col-span-2">
              <span className="label">{t("home.output")}</span>
              <Input
                autoComplete="off"
                spellCheck={false}
                disabled={processMutation.isPending}
                value={outputPath}
                placeholder={t("home.output_placeholder")}
                onChange={(event) => {
                  setOutputPath(event.currentTarget.value);
                  processMutation.reset();
                  setConfirmationArmed(false);
                }}
              />
            </label>
          </div>

          <p className="text-sm text-warning">{t("home.text_only_notice")}</p>
          <p className="text-sm text-fg-dim">{t("home.write_notice")}</p>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              variant="primary"
              disabled={!sourcePath.trim() || !trackerPath.trim() || previewMutation.isPending}
              onClick={analyze}
            >
              {previewMutation.isPending ? (
                <RotateCcw aria-hidden="true" className="h-4 w-4 animate-spin" />
              ) : (
                <FileSearch aria-hidden="true" className="h-4 w-4" />
              )}
              {previewMutation.isPending ? t("home.analyzing") : t("home.analyze")}
            </Button>
            {preview && <Badge variant="info">{t("home.pdf_count", { count: preview.records.length })}</Badge>}
          </div>
          {previewMutation.error && (
            <p className="text-sm text-danger" role="alert">
              {errorMessage(previewMutation.error, t("home.unknown_error"))}
            </p>
          )}
        </CardContent>
      </Card>

      {preview && (
        <section aria-label={t("home.preview_title")} className="flex flex-col gap-5">
          <div>
            <h2 className="font-display text-xl text-fg">{t("home.preview_title")}</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem_auto] sm:items-end">
              <label className="flex flex-col gap-1">
                <span className="label">{t("home.sheet")}</span>
                <Select
                  value={sheetName}
                  options={preview.sheet_names.map((name) => ({ value: name, label: name }))}
                  onChange={(event) => {
                    setSheetName(event.currentTarget.value);
                    setConfirmationArmed(false);
                  }}
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="label">{t("home.header_row")}</span>
                <Input
                  type="number"
                  min={1}
                  value={headerRow}
                  onChange={(event) => {
                    setHeaderRow(event.currentTarget.value);
                    setConfirmationArmed(false);
                  }}
                />
              </label>
              <Button
                type="button"
                variant="secondary"
                disabled={previewMutation.isPending || !sheetName || Number(headerRow) < 1}
                onClick={analyze}
              >
                <RotateCcw aria-hidden="true" className="h-4 w-4" />
                {t("home.reanalyze")}
              </Button>
            </div>
            {layoutDirty && <p className="mt-2 text-sm text-warning">{t("home.stale_layout")}</p>}
          </div>

          {preview.records.map((record, recordIndex) => {
            const hasFolderMetadata = Boolean(record.reference.trim() && record.subject.trim());
            return (
              <article key={record.source_path} className="border-t border-md py-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="font-medium text-fg">{record.file_name}</h3>
                  <Badge variant={hasFolderMetadata ? "info" : "warning"}>
                    {hasFolderMetadata ? t("home.ready") : t("home.missing_metadata")}
                  </Badge>
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {(["reference", "revision", "subject"] as const).map((field) => (
                    <label key={field} className="flex flex-col gap-1">
                      <span className="label">{t(`home.${field}`)}</span>
                      <Input
                        value={record[field]}
                        onChange={(event) => updateFolderField(recordIndex, field, event.currentTarget.value)}
                      />
                    </label>
                  ))}
                </div>
                <p className="mt-3 break-all text-sm text-fg-dim">
                  {t("home.folder")}: <code className="font-mono text-fg">{folderName(record) || t("home.missing_metadata")}</code>
                </p>
                <details open className="mt-4">
                  <summary className="cursor-pointer text-sm font-medium text-fg">
                    {t("home.tracker_values", { count: preview.columns.length })}
                  </summary>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {preview.columns.map((column, columnIndex) => (
                      <label key={`${column.index}-${column.name}`} className="flex flex-col gap-1">
                        <span className="label">{column.name}</span>
                        <Input
                          value={record.tracker_values[columnIndex] ?? ""}
                          onChange={(event) => updateTrackerValue(recordIndex, columnIndex, event.currentTarget.value)}
                        />
                      </label>
                    ))}
                  </div>
                </details>
              </article>
            );
          })}

          {preview.records.length === 0 && <p className="text-sm text-fg-dim">{t("home.empty_preview")}</p>}
          <div className="flex flex-wrap items-center gap-3 border-t border-md pt-4">
            <Button
              type="button"
              variant="primary"
              className="max-w-full whitespace-normal text-left"
              disabled={!readyToProcess || processMutation.isPending}
              onClick={confirmProcess}
            >
              <FolderPlus aria-hidden="true" className="h-4 w-4" />
              {processMutation.isPending
                ? t("home.processing")
                : confirmationArmed
                  ? t("home.confirm")
                  : t("home.process")}
            </Button>
            {processMutation.isSuccess && (
              <p className="text-sm text-success" role="status">
                {t("home.process_success", { count: processMutation.data.rows_written })}
              </p>
            )}
            {processMutation.error && (
              <p className="text-sm text-danger" role="alert">
                {errorMessage(processMutation.error, t("home.unknown_error"))}
              </p>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
