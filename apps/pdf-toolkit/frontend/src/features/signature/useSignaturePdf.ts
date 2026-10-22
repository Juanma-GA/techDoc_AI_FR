import { useEffect, useRef, useState } from "react";
import {
  GlobalWorkerOptions,
  getDocument,
  type PDFDocumentProxy,
  type PDFPageProxy,
} from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export type PreviewStatus = "empty" | "loading" | "ready" | "failed" | "no-pages";

export function useSignaturePdf(
  file: File | null,
  pageNumber: number,
  onPageCount: (count: number) => void,
  onReady: (ready: boolean) => void,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [documentProxy, setDocumentProxy] = useState<PDFDocumentProxy | null>(null);
  const [status, setStatus] = useState<PreviewStatus>("empty");
  const [pageSize, setPageSize] = useState({ width: 1, height: 1 });

  useEffect(() => {
    setDocumentProxy(null);
    setStatus(file ? "loading" : "empty");
    setPageSize({ width: 1, height: 1 });
    onPageCount(0);
    onReady(false);
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
      onPageCount(loaded.numPages);
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
  }, [file, onPageCount, onReady]);

  useEffect(() => {
    if (!documentProxy || pageNumber < 1 || pageNumber > documentProxy.numPages) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    let active = true;
    let renderTask: ReturnType<PDFPageProxy["render"]> | null = null;
    setStatus("loading");
    onReady(false);

    const renderPage = async () => {
      const page = await documentProxy.getPage(pageNumber);
      try {
        if (!active) return;
        const naturalSize = page.getViewport({ scale: 1 });
        const scale = Math.min(1.6, 3000 / Math.max(naturalSize.width, naturalSize.height));
        const viewport = page.getViewport({ scale });
        const context = canvas.getContext("2d");
        if (!context) {
          throw new Error("PDF preview canvas is unavailable");
        }
        canvas.width = Math.max(1, Math.ceil(viewport.width));
        canvas.height = Math.max(1, Math.ceil(viewport.height));
        setPageSize({ width: viewport.width, height: viewport.height });
        renderTask = page.render({ canvasContext: context, viewport });
        await renderTask.promise;
        if (active) {
          setStatus("ready");
          onReady(true);
        }
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
  }, [documentProxy, pageNumber, onReady]);

  return { canvasRef, hasDocument: documentProxy !== null, pageSize, status };
}
