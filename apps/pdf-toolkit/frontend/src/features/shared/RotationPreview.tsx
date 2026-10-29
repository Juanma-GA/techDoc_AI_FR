import { useEffect, useRef, useState } from "react";
import { RotateCw } from "lucide-react";
import {
  GlobalWorkerOptions,
  getDocument,
  type PDFDocumentProxy,
  type PDFPageProxy,
} from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { useTranslation } from "react-i18next";

import { Spinner } from "@internal/ui";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

type RotationPreviewProps = {
  file: File | null;
  pageNumber: number;
  rotation: number;
};

type PreviewStatus = "empty" | "loading" | "ready" | "failed" | "no-pages";

export function RotationPreview({ file, pageNumber, rotation }: RotationPreviewProps) {
  const { t } = useTranslation();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [pdfDocument, setPdfDocument] = useState<PDFDocumentProxy | null>(null);
  const [status, setStatus] = useState<PreviewStatus>("empty");

  useEffect(() => {
    setPdfDocument(null);
    setStatus(file ? "loading" : "empty");
    if (!file) return;

    let active = true;
    let loadingTask: ReturnType<typeof getDocument> | null = null;
    let loadedDocument: PDFDocumentProxy | null = null;
    void file
      .arrayBuffer()
      .then((buffer) => {
        if (!active) return null;
        loadingTask = getDocument({ data: new Uint8Array(buffer) });
        return loadingTask.promise;
      })
      .then((documentProxy) => {
        if (!documentProxy) return;
        if (!active) {
          void documentProxy.destroy();
          return;
        }
        loadedDocument = documentProxy;
        setPdfDocument(documentProxy);
        setStatus(documentProxy.numPages > 0 ? "loading" : "no-pages");
      })
      .catch(() => {
        if (active) setStatus("failed");
      });

    return () => {
      active = false;
      if (loadedDocument) {
        void loadedDocument.destroy();
      } else if (loadingTask) {
        void loadingTask.destroy();
      }
    };
  }, [file]);

  useEffect(() => {
    if (!pdfDocument) return;
    if (pdfDocument.numPages < 1) return;
    if (pageNumber < 1 || pageNumber > pdfDocument.numPages) {
      setStatus("failed");
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;
    let active = true;
    let renderTask: ReturnType<PDFPageProxy["render"]> | null = null;
    setStatus("loading");

    const renderPage = async () => {
      const page = await pdfDocument.getPage(pageNumber);
      try {
        if (!active) return;
        const pageRotation = (page.rotate + rotation) % 360;
        const unscaledViewport = page.getViewport({ scale: 1, rotation: pageRotation });
        const scale = Math.min(1.35, 560 / unscaledViewport.width, 480 / unscaledViewport.height);
        const viewport = page.getViewport({ scale, rotation: pageRotation });
        const context = canvas.getContext("2d");
        if (!context) throw new Error("PDF preview canvas is unavailable");

        canvas.width = Math.max(1, Math.ceil(viewport.width));
        canvas.height = Math.max(1, Math.ceil(viewport.height));
        renderTask = page.render({ canvasContext: context, viewport });
        await renderTask.promise;
        if (active) setStatus("ready");
      } finally {
        page.cleanup();
      }
    };
    void renderPage().catch(() => {
      if (active) setStatus("failed");
    });

    return () => {
      active = false;
      renderTask?.cancel();
    };
  }, [pageNumber, pdfDocument, rotation]);

  return (
    <div className="rotation-preview">
      <p className="input-help">{t("rotate.previewPage", { page: pageNumber })}</p>
      {status === "empty" ? (
        <div className="thumbnail-empty">
          <RotateCw size={22} aria-hidden="true" />
          <span>{t("rotate.previewEmpty")}</span>
        </div>
      ) : null}
      {status === "loading" ? (
        <p className="preview-status" role="status">
          <Spinner aria-label={t("common.loading")} />
          {t("rotate.previewLoading")}
        </p>
      ) : null}
      {status === "failed" ? (
        <p className="feedback feedback-error" role="alert">
          {t("rotate.previewFailed")}
        </p>
      ) : null}
      {status === "no-pages" ? (
        <p className="feedback feedback-error" role="alert">
          {t("rotate.emptyDocument")}
        </p>
      ) : null}
      {pdfDocument && status !== "failed" && status !== "no-pages" ? (
        <div className="rotation-preview-frame">
          <canvas
            ref={canvasRef}
            aria-label={t("rotate.previewCanvasLabel", {
              page: pageNumber,
              angle: rotation,
            })}
          />
        </div>
      ) : null}
    </div>
  );
}
