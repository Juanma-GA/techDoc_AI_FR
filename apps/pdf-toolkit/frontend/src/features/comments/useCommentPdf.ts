import { useCallback, useEffect, useRef, useState } from "react";
import {
  GlobalWorkerOptions,
  getDocument,
  type PDFDocumentProxy,
  type PDFPageProxy,
} from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export type CommentPreviewStatus = "empty" | "loading" | "ready" | "failed" | "no-pages";

type PageViewport = ReturnType<PDFPageProxy["getViewport"]>;

export function useCommentPdf(file: File | null, pageNumber: number) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderedPageRef = useRef<{ page: PDFPageProxy; viewport: PageViewport } | null>(null);
  const [documentProxy, setDocumentProxy] = useState<PDFDocumentProxy | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [pageSize, setPageSize] = useState({ width: 1, height: 1 });
  const [status, setStatus] = useState<CommentPreviewStatus>("empty");

  useEffect(() => {
    setDocumentProxy(null);
    setPageCount(0);
    setPageSize({ width: 1, height: 1 });
    renderedPageRef.current = null;
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
      setPageCount(loaded.numPages);
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
    if (!documentProxy || pageNumber < 1 || pageNumber > documentProxy.numPages) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    let active = true;
    let renderTask: ReturnType<PDFPageProxy["render"]> | null = null;
    setStatus("loading");
    renderedPageRef.current = null;

    const renderPage = async () => {
      const page = await documentProxy.getPage(pageNumber);
      try {
        if (!active) return;
        const naturalViewport = page.getViewport({ scale: 1 });
        const scale = Math.min(1.6, 3000 / Math.max(naturalViewport.width, naturalViewport.height));
        const viewport = page.getViewport({ scale });
        const context = canvas.getContext("2d");
        if (!context) throw new Error("PDF preview canvas is unavailable");
        canvas.width = Math.max(1, Math.ceil(viewport.width));
        canvas.height = Math.max(1, Math.ceil(viewport.height));
        setPageSize({ width: naturalViewport.width, height: naturalViewport.height });
        renderTask = page.render({ canvasContext: context, viewport });
        await renderTask.promise;
        if (active) {
          renderedPageRef.current = { page, viewport: naturalViewport };
          setStatus("ready");
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
  }, [documentProxy, pageNumber]);

  const convertPosition = useCallback(async (pageNumber: number, x: number, y: number) => {
    if (!documentProxy) throw new Error("PDF document is not ready");
    const page = await documentProxy.getPage(pageNumber);
    try {
      const viewport = page.getViewport({ scale: 1 });
      return viewport.convertToPdfPoint(x * viewport.width, y * viewport.height);
    } finally {
      page.cleanup();
    }
  }, [documentProxy]);

  return { canvasRef, convertPosition, pageCount, pageSize, status };
}
