import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { FileText, Image } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button, Card, Input, Select, Spinner } from "@internal/ui";
import {
  chooseExportDestination,
  saveExportBlob,
  validateExportFileName,
  type ExportProgressState,
} from "../../shared/api";
import { ExportProgress } from "../shared/ExportProgress";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { renderPdfImages, type RasterFormat } from "./renderPdfImages";

export function PdfToImagesTool() {
  const { t } = useTranslation();
  const formatSelectId = useId();
  const outputNameId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState<RasterFormat>("png");
  const [outputName, setOutputName] = useState("pdf-images.zip");
  const [exportProgress, setExportProgress] = useState<ExportProgressState>({
    phase: "preparing",
    percentage: null,
  });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [working, setWorking] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      controllerRef.current?.abort();
    },
    [],
  );

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError(t("files.select"));
      return;
    }
    const fileName = outputName.trim();
    const nameError = validateExportFileName(fileName);
    if (nameError) {
      setError(t(`exportOptions.${nameError}`));
      return;
    }

    const destinationChoice = chooseExportDestination(fileName, t);
    const controller = new AbortController();
    controllerRef.current = controller;
    setWorking(true);
    setExportProgress({ phase: "preparing", percentage: null });
    setError("");
    setSuccess(false);
    try {
      const destination = await destinationChoice;
      if (destination === null) return;
      const archive = await renderPdfImages(
        file,
        format,
        (completed, total) =>
          setExportProgress({
            phase: "pages",
            percentage: Math.round((completed / total) * 100),
            completed,
            total,
          }),
        controller.signal,
        {
          emptyDocument: t("pdfToImages.emptyDocument"),
          canvasUnavailable: t("pdfToImages.canvasUnavailable"),
          renderFailed: t("pdfToImages.failed"),
          archiveFailed: t("pdfToImages.archiveFailed"),
        },
      );
      if (controller.signal.aborted) {
        return;
      }
      const savedName = await saveExportBlob(archive, fileName, destination, t);
      setOutputName(savedName);
      setSuccess(true);
    } catch (reason) {
      if (!controller.signal.aborted) {
        setError(reason instanceof Error ? reason.message : t("pdfToImages.failed"));
      }
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setWorking(false);
      }
    }
  };

  return (
    <form className="workflow-grid" onSubmit={submit}>
      <Card className="panel">
        <div className="panel-heading">
          <span className="step-number">01</span>
          <div>
            <h2>{t("pdfToImages.stepFile")}</h2>
            <p>{t("pdfToImages.stepFileDescription")}</p>
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
            </span>
          </div>
        ) : null}
      </Card>

      <Card className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("pdfToImages.stepOutput")}</h2>
            <p>{t("pdfToImages.stepOutputDescription")}</p>
          </div>
        </div>
        <label className="field-label" htmlFor={formatSelectId}>
          {t("pdfToImages.formatLabel")}
        </label>
        <Select
          id={formatSelectId}
          options={[
            { value: "png", label: t("pdfToImages.png") },
            { value: "jpeg", label: t("pdfToImages.jpeg") },
          ]}
          value={format}
          disabled={working}
          onChange={(event) => {
            const nextFormat = event.currentTarget.value;
            if (isRasterFormat(nextFormat)) {
              setFormat(nextFormat);
              setSuccess(false);
            }
          }}
        />
        <div className="output-preview">
          <span className="output-icon">
            <Image size={21} aria-hidden="true" />
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
            <small>{t("pdfToImages.stepOutputDescription")}</small>
          </span>
        </div>
        <p className="input-help" id={`${outputNameId}-help`}>
          {t("exportOptions.saveLocationHint")}
        </p>
        {working ? <ExportProgress progress={exportProgress} /> : null}
        <Button type="submit" disabled={working || !file} className="action-button">
          {working ? <Spinner aria-label={t("common.loading")} /> : <Image size={18} />}
          {working ? t("pdfToImages.working") : t("pdfToImages.action")}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {success ? (
            <p className="feedback feedback-success" role="status">
              {t("pdfToImages.success", { fileName: outputName })}
            </p>
          ) : null}
        </div>
      </Card>
    </form>
  );
}

function isRasterFormat(value: string): value is RasterFormat {
  return value === "png" || value === "jpeg";
}
