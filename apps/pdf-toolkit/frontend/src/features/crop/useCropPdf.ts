import { useEffect, useRef, useState } from "react";
import {
  GlobalWorkerOptions,
  getDocument,
  type PDFDocumentProxy,
  type PDFPageProxy,
} from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export type CropPreviewStatus = "empty" | "loading" | "ready" | "failed" | "no-pages";

export function useCropPdf(file: File | null) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [documentProxy, setDocumentProxy] = useState<PDFDocumentProxy | null>(null);
  const [pageSize, setPageSize] = useState({ width: 1, height: 1 });
  const [status, setStatus] = useState<CropPreviewStatus>("empty");

  useEffect(() => {
    setDocumentProxy(null);
    setPageSize({ width: 1, height: 1 });
    setStatus(file ? "loading" : "empty");
    if (!file) return;

    let active = true;
    let loadingTask: ReturnType<typeof getDocument> | null = null;
    let loadedDocument: PDFDocumentProxy | null = null;
    const loadDocument = async () => {
      const data = new Uint8Array(await file.arrayBuffer());
      if (!active) return;
      loadingTask = getDocument({ data });
      const loaded = await loadingTask.promise;
      if (!active) {
        await loaded.destroy();
        return;
      }
      if (loaded.numPages < 1) {
        setStatus("no-pages");
        await loaded.destroy();
        return;
      }
      loadedDocument = loaded;
      setDocumentProxy(loaded);
    };
    void loadDocument().catch(() => {
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
    if (!documentProxy) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    let active = true;
    let renderTask: ReturnType<PDFPageProxy["render"]> | null = null;
    setStatus("loading");

    const renderFirstPage = async () => {
      const page = await documentProxy.getPage(1);
      try {
        if (!active) return;
        const naturalViewport = page.getViewport({ scale: 1 });
        const scale = Math.min(1.6, 1400 / Math.max(naturalViewport.width, naturalViewport.height));
        const viewport = page.getViewport({ scale });
        const context = canvas.getContext("2d");
        if (!context) throw new Error("PDF preview canvas is unavailable");
        canvas.width = Math.max(1, Math.ceil(viewport.width));
        canvas.height = Math.max(1, Math.ceil(viewport.height));
        setPageSize({ width: naturalViewport.width, height: naturalViewport.height });
        renderTask = page.render({ canvasContext: context, viewport, background: "white" });
        await renderTask.promise;
        if (active) setStatus("ready");
      } finally {
        page.cleanup();
      }
    };
    void renderFirstPage().catch(() => {
      if (active) setStatus("failed");
    });

    return () => {
      active = false;
      renderTask?.cancel();
    };
  }, [documentProxy]);

  return { canvasRef, documentProxy, pageSize, status };
}
