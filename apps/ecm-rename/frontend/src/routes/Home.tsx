import { useMutation } from "@tanstack/react-query";
import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input, Select } from "@internal/ui";
import { Check, FileSearch, FolderPlus, ListPlus, RotateCcw } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { usePathPreferences } from "../hooks/usePathPreferences";
import {
  ecmRenameApi,
  type BrowseKind,
  type PreviewDto,
  type PreviewRequest,
  type AppendTrackerDto,
  type CreateFoldersDto,
  type TrackerField,
} from "../lib/api";
import { PathPickerField } from "./PathPickerField";
import { ProcessResult } from "./ProcessResult";

type FolderField = Extract<TrackerField, "reference" | "revision" | "subject">;
type Operation = "folders" | "tracker";

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

type HomeProps = {
  folderResult: CreateFoldersDto | null;
  trackerResult: AppendTrackerDto | null;
  onFoldersCreated: (result: CreateFoldersDto) => void;
  onTrackerUpdated: (result: AppendTrackerDto) => void;
  onClearResults: () => void;
  onClearFolderResult: () => void;
  onClearTrackerResult: () => void;
};

export function Home({
  folderResult,
  trackerResult,
  onFoldersCreated,
  onTrackerUpdated,
  onClearResults,
  onClearFolderResult,
  onClearTrackerResult,
}: HomeProps) {
  const { t, i18n } = useTranslation();
  const pathPreferences = usePathPreferences();
  const {
    source_path: sourcePath,
    tracker_path: trackerPath,
    output_path: outputPath,
  } = pathPreferences.paths;
  const [sheetName, setSheetName] = useState("");
  const [headerRow, setHeaderRow] = useState("");
  const [preview, setPreview] = useState<PreviewDto | null>(null);

  const previewMutation = useMutation({
    mutationFn: ecmRenameApi.preview,
    onSuccess: (result) => {
      setPreview(result);
      setSheetName(result.sheet_name);
      setHeaderRow(String(result.header_row));
      folderMutation.reset();
      trackerMutation.reset();
    },
  });

  const folderMutation = useMutation({
    mutationFn: ecmRenameApi.createFolders,
    onSuccess: onFoldersCreated,
  });

  const trackerMutation = useMutation({
    mutationFn: ecmRenameApi.appendTracker,
    onSuccess: onTrackerUpdated,
  });

  const browseMutation = useMutation({
    mutationFn: ecmRenameApi.browse,
    onSuccess: ({ path }, request) => {
      if (!path) return;
      if (request.kind === "source_file" || request.kind === "source_directory") {
        pathPreferences.savePaths({ source_path: path });
        clearPreview();
        return;
      }
      if (request.kind === "tracker_file") {
        pathPreferences.savePaths({ tracker_path: path });
        clearPreview();
        return;
      }
      pathPreferences.savePaths({ output_path: path });
      onClearFolderResult();
      folderMutation.reset();
    },
  });

  const layoutDirty = Boolean(
    preview && (preview.sheet_name !== sheetName || preview.header_row !== Number(headerRow)),
  );
  const readyForFolders = Boolean(
    preview &&
      outputPath.trim() &&
      !layoutDirty &&
      preview.records.length > 0 &&
      preview.records.every((record) => record.reference.trim() && record.subject.trim()),
  );
  const readyForTracker = Boolean(
    preview &&
      !layoutDirty &&
      preview.records.length > 0 &&
      preview.records.every((record) => record.tracker_values.length === preview.columns.length),
  );
  const operationPending = folderMutation.isPending || trackerMutation.isPending;

  function clearPreview() {
    onClearResults();
    setPreview(null);
    setSheetName("");
    setHeaderRow("");
    previewMutation.reset();
    folderMutation.reset();
    trackerMutation.reset();
  }

  function analyze() {
    onClearResults();
    const request: PreviewRequest = {
      source_path: sourcePath.trim(),
      tracker_path: trackerPath.trim(),
    };
    if (sheetName) request.sheet_name = sheetName;
    if (preview && headerRow) request.header_row = Number(headerRow);
    previewMutation.mutate(request);
  }

  function browse(kind: BrowseKind) {
    const currentPath =
      kind === "source_file" || kind === "source_directory"
        ? sourcePath
        : kind === "tracker_file"
          ? trackerPath
          : outputPath;
    const language = i18n.resolvedLanguage?.startsWith("en") ? "en" : "fr";
    browseMutation.mutate({ kind, current_path: currentPath || undefined, language });
  }

  function updateFolderField(recordIndex: number, field: FolderField, value: string) {
    onClearFolderResult();
    onClearTrackerResult();
    folderMutation.reset();
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
    const selectedField = preview?.columns[columnIndex]?.field;
    onClearTrackerResult();
    if (selectedField === "reference" || selectedField === "revision" || selectedField === "subject") {
      onClearFolderResult();
      folderMutation.reset();
    }
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

  function runOperation(operation: Operation) {
    const ready = operation === "folders" ? readyForFolders : readyForTracker;
    if (!preview || !ready) return;
    if (operation === "folders") {
      if (folderResult) return;
      folderMutation.mutate({
        source_path: preview.source_path,
        output_path: outputPath.trim(),
        records: preview.records.map(({ source_path, reference, revision, subject }) => ({
          source_path,
          reference,
          revision,
          subject,
        })),
      });
      return;
    }

    trackerMutation.mutate({
      tracker_path: preview.tracker_path,
      sheet_name: preview.sheet_name,
      header_row: preview.header_row,
      records: preview.records.map(({ tracker_values }) => ({ tracker_values })),
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
            <PathPickerField
              field="source"
              label={t("home.source")}
              placeholder={t("home.source_placeholder")}
              value={sourcePath}
              disabled={
                pathPreferences.isLoading ||
                previewMutation.isPending ||
                operationPending ||
                browseMutation.isPending
              }
              onChange={(value) => {
                pathPreferences.setPath("source_path", value);
                clearPreview();
              }}
              onBlur={() => pathPreferences.savePaths()}
              onBrowse={browse}
            />
            <PathPickerField
              field="tracker"
              label={t("home.tracker")}
              placeholder={t("home.tracker_placeholder")}
              value={trackerPath}
              disabled={
                pathPreferences.isLoading ||
                previewMutation.isPending ||
                operationPending ||
                browseMutation.isPending
              }
              onChange={(value) => {
                pathPreferences.setPath("tracker_path", value);
                clearPreview();
              }}
              onBlur={() => pathPreferences.savePaths()}
              onBrowse={browse}
            />
            <div className="md:col-span-2">
              <PathPickerField
                field="output"
                label={t("home.output")}
                placeholder={t("home.output_placeholder")}
                value={outputPath}
                disabled={pathPreferences.isLoading || operationPending || browseMutation.isPending}
                onChange={(value) => {
                  pathPreferences.setPath("output_path", value);
                  onClearFolderResult();
                  folderMutation.reset();
                }}
                onBlur={() => pathPreferences.savePaths()}
                onBrowse={browse}
              />
            </div>
          </div>

          {pathPreferences.loadError && (
            <p className="text-sm text-danger" role="alert">
              {errorMessage(pathPreferences.loadError, t("home.paths_load_failed"))}
            </p>
          )}
          {pathPreferences.saveError && (
            <p className="text-sm text-danger" role="alert">
              {errorMessage(pathPreferences.saveError, t("home.paths_save_failed"))}
            </p>
          )}
          {browseMutation.error && (
            <p className="text-sm text-danger" role="alert">
              {errorMessage(browseMutation.error, t("home.browse_failed"))}
            </p>
          )}
          <p className="text-sm text-fg-dim">{t("home.write_notice")}</p>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              variant="primary"
              disabled={
                !sourcePath.trim() || !trackerPath.trim() || previewMutation.isPending || browseMutation.isPending
                || operationPending
              }
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
          <div className="flex flex-wrap items-start gap-3 border-t border-md pt-4">
            <div className="flex flex-col gap-2">
              <Button
                type="button"
                variant={folderResult ? "secondary" : "primary"}
                className="max-w-full whitespace-normal text-left"
                disabled={!readyForFolders || operationPending || browseMutation.isPending || Boolean(folderResult)}
                onClick={() => runOperation("folders")}
              >
                {folderResult ? (
                  <Check aria-hidden="true" className="h-4 w-4" />
                ) : folderMutation.isPending ? (
                  <RotateCcw aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : (
                  <FolderPlus aria-hidden="true" className="h-4 w-4" />
                )}
                {folderResult
                  ? t("home.folders_done")
                  : folderMutation.isPending
                    ? t("home.creating_folders")
                    : t("home.create_folders")}
              </Button>
              {folderMutation.error && (
                <p className="max-w-sm text-sm text-danger" role="alert">
                  {errorMessage(folderMutation.error, t("home.unknown_error"))}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <Button
                type="button"
                variant="secondary"
                className="max-w-full whitespace-normal text-left"
                disabled={!readyForTracker || operationPending || browseMutation.isPending || Boolean(trackerResult)}
                onClick={() => runOperation("tracker")}
              >
                {trackerMutation.isPending ? (
                  <RotateCcw aria-hidden="true" className="h-4 w-4 animate-spin" />
                ) : trackerResult ? (
                  <Check aria-hidden="true" className="h-4 w-4" />
                ) : (
                  <ListPlus aria-hidden="true" className="h-4 w-4" />
                )}
                {trackerMutation.isPending
                  ? t("home.appending_tracker")
                  : trackerResult
                    ? t("home.tracker_done")
                    : t("home.append_tracker")}
              </Button>
              {trackerMutation.error && (
                <p className="max-w-sm text-sm text-danger" role="alert">
                  {errorMessage(trackerMutation.error, t("home.unknown_error"))}
                </p>
              )}
            </div>
          </div>
        </section>
      )}
      {(folderResult || trackerResult) && (
        <ProcessResult folderResult={folderResult} trackerResult={trackerResult} />
      )}
    </div>
  );
}
