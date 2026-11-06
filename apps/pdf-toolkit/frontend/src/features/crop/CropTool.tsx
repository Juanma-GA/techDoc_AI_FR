import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Crop, FileText } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button, Card, Input, Select, Spinner } from "@internal/ui";
import {
  chooseExportDestination,
  formatOperationError,
  processPDF,
  validateExportFileName,
  type ExportProgressState,
} from "../../shared/api";
import { ExportProgress } from "../shared/ExportProgress";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";
import { CropPagePreview } from "./CropPagePreview";
import {
  buildPageCropRectangles,
  type CropMode,
  type CropRegion,
} from "./cropGeometry";
import { useCropPdf } from "./useCropPdf";
import "./crop.css";

const FULL_PAGE: CropRegion = { left: 0, top: 0, right: 1, bottom: 1 };
const REGION_EPSILON = 0.005;

type CropField = "left" | "top" | "width" | "height";

export function CropTool() {
  const { t, i18n } = useTranslation();
  const modeId = useId();
  const outputNameId = useId();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<CropMode>("manual");
  const [region, setRegion] = useState<CropRegion>(FULL_PAGE);
  const [outputName, setOutputName] = useState("cropped.pdf");
  const [exportProgress, setExportProgress] = useState<ExportProgressState>({
    phase: "uploading",
    percentage: 0,
  });
  const [analysisProgress, setAnalysisProgress] = useState<{ completed: number; total: number } | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);
  const preview = useCropPdf(file);
  const hasManualCrop = removesMargins(region);

  useEffect(
    () => () => {
      controllerRef.current?.abort();
    },
    [],
  );

  const updateRegionField = (field: CropField, value: number) => {
    if (!Number.isFinite(value)) return;
    const normalized = Math.min(1, Math.max(0, value / 100));
    setRegion((current) => {
      const minimum = 0.01;
      if (field === "left") {
        const left = Math.min(normalized, current.right - minimum);
        return { ...current, left: Math.max(0, left) };
      }
      if (field === "top") {
        const top = Math.min(normalized, current.bottom - minimum);
        return { ...current, top: Math.max(0, top) };
      }
      if (field === "width") {
        return { ...current, right: Math.min(1, current.left + Math.max(minimum, normalized)) };
      }
      return { ...current, bottom: Math.min(1, current.top + Math.max(minimum, normalized)) };
    });
    setSuccess(false);
    setError("");
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file || !preview.documentProxy || preview.status !== "ready") {
      setError(t("crop.previewRequired"));
      return;
    }
    if (mode === "manual" && !hasManualCrop) {
      setError(t("crop.selectionRequired"));
      return;
    }
    const fileName = outputName.trim();
    const nameError = validateExportFileName(fileName);
    if (nameError) {
      setError(t(`exportOptions.${nameError}`));
      return;
    }

    const controller = new AbortController();
    controllerRef.current?.abort();
    controllerRef.current = controller;
    setWorking(true);
    setAnalysisProgress({ completed: 0, total: preview.documentProxy.numPages });
    setError("");
    setSuccess(false);

    try {
      const destination = await chooseExportDestination(fileName, t);
      if (destination === null) return;
      const result = await buildPageCropRectangles(
        preview.documentProxy,
        mode,
        region,
        controller.signal,
        (completed, total) => setAnalysisProgress({ completed, total }),
      );
      if (controller.signal.aborted) return;
      if (result.changedPages === 0) {
        setError(t("crop.noMarginsFound"));
        return;
      }

      setAnalysisProgress(null);
      const data = new FormData();
      data.append("file", file, file.name);
      data.append("crops", JSON.stringify(result.rectangles));
      const savedName = await processPDF(
        "crop",
        data,
        fileName,
        t,
        setExportProgress,
        destination ?? undefined,
      );
      setOutputName(savedName);
      setSuccess(true);
    } catch (reason) {
      if (!controller.signal.aborted) {
        setError(formatOperationError(reason, t, "crop.failed"));
      }
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setAnalysisProgress(null);
        setWorking(false);
      }
    }
  };

  const previewRegion = mode === "manual" && hasManualCrop ? region : null;

  return (
    <form className="workflow-grid crop-workflow" onSubmit={handleSubmit}>
      <Card className="panel crop-preview-panel">
        <div className="panel-heading">
          <span className="step-number">01</span>
          <div>
            <h2>{t("crop.stepFile")}</h2>
            <p>{t("crop.stepFileDescription")}</p>
          </div>
        </div>
        <FileDropzone
          disabled={working}
          onFiles={(incoming) => {
            const nextFile = incoming[0] ?? null;
            setFile(nextFile);
            setRegion(FULL_PAGE);
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
          </div>
        ) : null}
        {preview.status === "loading" && file ? (
          <p className="preview-status" role="status">
            <Spinner aria-label={t("common.loading")} />
            {t("crop.previewLoading")}
          </p>
        ) : null}
        {preview.status === "failed" || preview.status === "no-pages" ? (
          <p className="feedback feedback-error" role="alert">
            {t(preview.status === "no-pages" ? "crop.noPages" : "crop.previewFailed")}
          </p>
        ) : null}
        {preview.documentProxy ? (
          <>
            <p className="input-help crop-preview-help">
              {t(mode === "manual" ? "crop.manualHelp" : "crop.automaticHelp")}
            </p>
            <CropPagePreview
              canvasRef={preview.canvasRef}
              pageSize={preview.pageSize}
              ready={preview.status === "ready"}
              disabled={working || mode !== "manual"}
              region={previewRegion}
              onRegionChange={(nextRegion) => {
                setRegion(nextRegion ?? FULL_PAGE);
                setSuccess(false);
                setError("");
              }}
            />
          </>
        ) : null}
      </Card>

      <Card className="panel action-panel crop-action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("crop.stepCrop")}</h2>
            <p>{t("crop.stepCropDescription")}</p>
          </div>
        </div>
        <label className="field-label" htmlFor={modeId}>
          {t("crop.modeLabel")}
        </label>
        <Select
          id={modeId}
          options={[
            { value: "manual", label: t("crop.manualMode") },
            { value: "automatic", label: t("crop.automaticMode") },
          ]}
          value={mode}
          disabled={working}
          onChange={(event) => {
            const nextMode = event.currentTarget.value;
            if (nextMode === "manual" || nextMode === "automatic") {
              setMode(nextMode);
              setError("");
              setSuccess(false);
            }
          }}
        />
        {mode === "manual" ? (
          <div className="crop-region-controls">
            <p className="input-help">{t("crop.manualScope")}</p>
            <div className="crop-region-fields">
              <CropRegionField
                label={t("crop.leftLabel")}
                value={region.left * 100}
                disabled={working || preview.status !== "ready"}
                onChange={(value) => updateRegionField("left", value)}
              />
              <CropRegionField
                label={t("crop.topLabel")}
                value={region.top * 100}
                disabled={working || preview.status !== "ready"}
                onChange={(value) => updateRegionField("top", value)}
              />
              <CropRegionField
                label={t("crop.widthLabel")}
                value={(region.right - region.left) * 100}
                disabled={working || preview.status !== "ready"}
                onChange={(value) => updateRegionField("width", value)}
              />
              <CropRegionField
                label={t("crop.heightLabel")}
                value={(region.bottom - region.top) * 100}
                disabled={working || preview.status !== "ready"}
                onChange={(value) => updateRegionField("height", value)}
              />
            </div>
            {!hasManualCrop && preview.status === "ready" ? (
              <p className="input-help">{t("crop.selectionRequired")}</p>
            ) : null}
          </div>
        ) : (
          <p className="input-help crop-auto-help">{t("crop.automaticScope")}</p>
        )}

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
            <small>{t("crop.outputDescription")}</small>
          </span>
        </div>
        <p className="input-help" id={`${outputNameId}-help`}>
          {t("exportOptions.saveLocationHint")}
        </p>
        {analysisProgress ? (
          <p className="crop-analysis-progress" role="status">
            <Spinner aria-label={t("common.loading")} />
            {t("crop.analysisProgress", analysisProgress)}
          </p>
        ) : working ? (
          <ExportProgress progress={exportProgress} />
        ) : null}
        <Button
          type="submit"
          disabled={
            working ||
            !file ||
            preview.status !== "ready" ||
            (mode === "manual" && !hasManualCrop)
          }
          className="action-button"
        >
          {working ? <Spinner aria-label={t("common.loading")} /> : <Crop size={18} />}
          {working ? t("crop.working") : t("crop.action")}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("crop.success", { fileName: outputName })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}

type CropRegionFieldProps = {
  label: string;
  value: number;
  disabled: boolean;
  onChange: (value: number) => void;
};

function CropRegionField({ label, value, disabled, onChange }: CropRegionFieldProps) {
  const id = useId();
  return (
    <label className="crop-region-field" htmlFor={id}>
      {label}
      <Input
        id={id}
        type="number"
        min={0}
        max={100}
        step={1}
        value={Math.round(value)}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.currentTarget.value))}
      />
    </label>
  );
}

function removesMargins(region: CropRegion): boolean {
  return (
    region.left > REGION_EPSILON ||
    region.top > REGION_EPSILON ||
    region.right < 1 - REGION_EPSILON ||
    region.bottom < 1 - REGION_EPSILON
  );
}
