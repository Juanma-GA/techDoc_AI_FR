import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";
import { Download, FileText, Image as ImageIcon, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button, Card, Input, Spinner } from "@internal/ui";
import {
  chooseExportDestination,
  formatOperationError,
  saveExportBlob,
  validateExportFileName,
  type ExportProgressState,
} from "../../shared/api";
import { FileDropzone } from "../../shared/components/FileDropzone";
import { formatFileSize } from "../../shared/files";
import { ExportProgress } from "../shared/ExportProgress";
import { checkReadablePdf } from "./checkReadablePdf";
import { extractImagesFromPDF } from "./extractImagesApi";
import {
  groupImagesByContent,
  unpackImageArchive,
  type ExtractedImageGroup,
  type ExtractedImage,
} from "./unpackImageArchive";
import "./extract-images.css";

export function ExtractImagesTool() {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language ?? "fr";
  const outputNameId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [outputName, setOutputName] = useState("extracted-images.zip");
  const [archive, setArchive] = useState<Blob | null>(null);
  const [images, setImages] = useState<ExtractedImage[]>([]);
  const [successFileName, setSuccessFileName] = useState("");
  const [error, setError] = useState("");
  const [downloadError, setDownloadError] = useState("");
  const [working, setWorking] = useState(false);
  const [checkingPdf, setCheckingPdf] = useState(false);
  const [savingArchive, setSavingArchive] = useState(false);
  const [exportProgress, setExportProgress] = useState<ExportProgressState>({
    phase: "preparing",
    percentage: null,
  });
  const imageGroups = useMemo(() => groupImagesByContent(images), [images]);
  const repeatedImageGroups = imageGroups.filter((group) => group.occurrences > 1);
  const uniqueImageGroups = imageGroups.filter((group) => group.occurrences === 1);
  const controllerRef = useRef<AbortController | null>(null);
  const imageUrlsRef = useRef<ExtractedImage[]>([]);

  useEffect(
    () => () => {
      controllerRef.current?.abort();
      revokeImages(imageUrlsRef.current);
      imageUrlsRef.current = [];
    },
    [],
  );

  const clearImages = () => {
    revokeImages(imageUrlsRef.current);
    imageUrlsRef.current = [];
    setImages([]);
    setArchive(null);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!file) {
      setError(t("files.select"));
      return;
    }

    const controller = new AbortController();
    controllerRef.current = controller;
    let extractedImages: ExtractedImage[] = [];
    clearImages();
    setWorking(true);
    setCheckingPdf(true);
    setExportProgress({ phase: "preparing", percentage: null });
    setError("");
    setDownloadError("");
    setSuccessFileName("");

    try {
      await checkReadablePdf(
        file,
        {
          unreadablePdf: t("extractImages.unreadablePdf"),
          noTextLayer: t("extractImages.noTextLayer"),
        },
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setCheckingPdf(false);

      const archive = await extractImagesFromPDF(file, t, setExportProgress, controller.signal);
      if (controller.signal.aborted) return;

      extractedImages = await unpackImageArchive(archive, {
        invalidArchive: t("extractImages.invalidArchive"),
        emptyArchive: t("extractImages.emptyArchive"),
      });
      if (controller.signal.aborted) return;

      imageUrlsRef.current = extractedImages;
      setImages(extractedImages);
      setArchive(archive);
      extractedImages = [];
    } catch (reason: unknown) {
      revokeImages(extractedImages);
      if (!controller.signal.aborted) {
        setError(formatOperationError(reason, t, "extractImages.failed"));
      }
    } finally {
      setCheckingPdf(false);
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setWorking(false);
      }
    }
  };

  const downloadArchive = async () => {
    if (!archive || images.length === 0 || savingArchive) return;

    const rawName = outputName.trim();
    const nameError = validateExportFileName(rawName);
    if (nameError) {
      setDownloadError(t(`exportOptions.${nameError}`));
      return;
    }

    const fileName = ensureZipExtension(rawName);
    setSavingArchive(true);
    setDownloadError("");
    setSuccessFileName("");

    try {
      const destination = await chooseExportDestination(fileName, t);
      if (destination === null) return;

      const savedName = await saveExportBlob(archive, fileName, destination, t);
      setOutputName(savedName);
      setSuccessFileName(savedName);
    } catch (reason: unknown) {
      setDownloadError(formatOperationError(reason, t, "extractImages.downloadFailed"));
    } finally {
      setSavingArchive(false);
    }
  };

  const renderImageGroup = ({ image, occurrences }: ExtractedImageGroup) => (
    <a
      key={image.contentHash}
      className="extract-images-download"
      href={image.url}
      download={image.name}
      aria-label={t("extractImages.downloadImage", { name: image.name })}
      title={t("extractImages.downloadImage", { name: image.name })}
    >
      <span className="extract-images-preview">
        {image.previewable ? (
          <img src={image.url} alt={image.name} loading="lazy" decoding="async" />
        ) : (
          <span className="extract-images-preview-unavailable">
            <ImageIcon size={30} aria-hidden="true" />
            <span>{t("extractImages.previewUnavailable")}</span>
          </span>
        )}
      </span>
      <span className="extract-images-name">{image.name}</span>
      {occurrences > 1 ? (
        <span className="extract-images-occurrences">
          {t("extractImages.repeatedOccurrences", { count: occurrences })}
        </span>
      ) : (
        <span className="extract-images-size">{formatFileSize(image.size, language)}</span>
      )}
    </a>
  );

  return (
    <form className="workflow-grid" onSubmit={submit}>
      <Card className="panel">
        <div className="panel-heading">
          <span className="step-number">01</span>
          <div>
            <h2>{t("extractImages.stepFile")}</h2>
            <p>{t("extractImages.stepFileDescription")}</p>
          </div>
        </div>
        <FileDropzone
          disabled={working || savingArchive}
          onFiles={(incoming) => {
            setFile(incoming[0] ?? null);
            clearImages();
            setError("");
            setDownloadError("");
            setSuccessFileName("");
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
              type="button"
              variant="ghost"
              className="icon-button remove-button"
              disabled={working || savingArchive}
              onClick={() => {
                setFile(null);
                clearImages();
                setError("");
                setDownloadError("");
                setSuccessFileName("");
              }}
              aria-label={t("files.remove")}
            >
              <X size={16} aria-hidden="true" />
            </Button>
          </div>
        ) : null}
      </Card>

      <Card className="panel action-panel">
        <div className="panel-heading">
          <span className="step-number">02</span>
          <div>
            <h2>{t("extractImages.stepOutput")}</h2>
            <p>{t("extractImages.stepOutputDescription")}</p>
          </div>
        </div>
        {working && !checkingPdf ? <ExportProgress progress={exportProgress} /> : null}
        <Button
          type="submit"
          disabled={working || savingArchive || !file}
          className="action-button"
        >
          {working ? <Spinner aria-label={t("common.loading")} /> : <ImageIcon size={18} />}
          {checkingPdf
            ? t("extractImages.checkingPdf")
            : working
              ? t("extractImages.working")
              : t("extractImages.action")}
        </Button>
        <div className="feedback-slot">
          {error ? (
            <p className="feedback feedback-error" role="alert">
              {error}
            </p>
          ) : null}
          {images.length > 0 ? (
            <p className="feedback feedback-success" role="status">
              {t("extractImages.extractedSuccess")}
            </p>
          ) : null}
        </div>
      </Card>

      {images.length > 0 ? (
        <Card className="panel extract-images-gallery">
          <section aria-labelledby="extract-images-gallery-title">
            <div className="extract-images-gallery-heading">
              <div>
                <h2 id="extract-images-gallery-title">
                  {t("extractImages.galleryTitle", { count: images.length })}
                </h2>
                <p>{t("extractImages.galleryDescription")}</p>
              </div>
            </div>
            <div className="output-preview">
              <span className="output-icon">
                <ImageIcon size={21} aria-hidden="true" />
              </span>
              <span>
                <label className="field-label" htmlFor={outputNameId}>
                  {t("exportOptions.fileName")}
                </label>
                <Input
                  id={outputNameId}
                  value={outputName}
                  disabled={savingArchive}
                  aria-describedby={`${outputNameId}-help`}
                  onChange={(event) => {
                    setOutputName(event.currentTarget.value);
                    setDownloadError("");
                    setSuccessFileName("");
                  }}
                />
                <small>{t("extractImages.outputDescription")}</small>
              </span>
            </div>
            <p className="input-help" id={`${outputNameId}-help`}>
              {t("exportOptions.saveLocationHint")}
            </p>
            <Button
              type="button"
              disabled={savingArchive}
              onClick={downloadArchive}
              className="action-button"
            >
              {savingArchive ? (
                <Spinner aria-label={t("common.loading")} />
              ) : (
                <Download size={18} />
              )}
              {savingArchive
                ? t("extractImages.downloadingArchive")
                : t("extractImages.downloadArchive")}
            </Button>
            <div className="feedback-slot">
              {downloadError ? (
                <p className="feedback feedback-error" role="alert">
                  {downloadError}
                </p>
              ) : null}
              {successFileName ? (
                <p className="feedback feedback-success" role="status">
                  {t("extractImages.downloadSuccess", { fileName: successFileName })}
                </p>
              ) : null}
            </div>
            {repeatedImageGroups.length > 0 ? (
              <section className="extract-images-category" aria-labelledby="extract-images-repeated-title">
                <h3 id="extract-images-repeated-title">{t("extractImages.repeatedTitle")}</h3>
                <p>{t("extractImages.repeatedDescription")}</p>
                <div className="extract-images-grid">{repeatedImageGroups.map(renderImageGroup)}</div>
              </section>
            ) : null}
            {uniqueImageGroups.length > 0 ? (
              <section className="extract-images-category" aria-labelledby="extract-images-unique-title">
                <h3 id="extract-images-unique-title">{t("extractImages.uniqueTitle")}</h3>
                <div className="extract-images-grid">{uniqueImageGroups.map(renderImageGroup)}</div>
              </section>
            ) : null}
          </section>
        </Card>
      ) : null}
    </form>
  );
}

function ensureZipExtension(name: string): string {
  return name.toLowerCase().endsWith(".zip") ? name : `${name}.zip`;
}

function revokeImages(images: ExtractedImage[]): void {
  images.forEach((image) => URL.revokeObjectURL(image.url));
}
