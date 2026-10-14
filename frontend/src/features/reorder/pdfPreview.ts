import { GlobalWorkerOptions, getDocument, type PDFDocumentProxy } from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export type PageThumbnail = {
  pageNumber: number;
  dataUrl: string;
};

export type PdfPreviewMessages = {
  emptyDocument: string;
  canvasUnavailable: string;
};

export async function renderPdfThumbnails(
  file: File,
  onProgress: (completed: number, total: number) => void,
  signal: AbortSignal,
  messages: PdfPreviewMessages,
): Promise<PageThumbnail[]> {
  const data = new Uint8Array(await file.arrayBuffer());
  if (signal.aborted) {
    throw new DOMException("Preview cancelled", "AbortError");
  }

  const loadingTask = getDocument({ data });
  const cancelLoading = () => {
    void loadingTask.destroy();
  };
  signal.addEventListener("abort", cancelLoading, { once: true });

  let documentProxy: PDFDocumentProxy | null = null;
  try {
    documentProxy = await loadingTask.promise;
    if (documentProxy.numPages < 1) {
      throw new Error(messages.emptyDocument);
    }

    const thumbnails: PageThumbnail[] = [];
    onProgress(0, documentProxy.numPages);
    for (let pageNumber = 1; pageNumber <= documentProxy.numPages; pageNumber += 1) {
      if (signal.aborted) {
        throw new DOMException("Preview cancelled", "AbortError");
      }

      const page = await documentProxy.getPage(pageNumber);
      const naturalSize = page.getViewport({ scale: 1 });
      const scale = Math.min(170 / naturalSize.width, 220 / naturalSize.height);
      const viewport = page.getViewport({ scale });
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d");
      if (!context) {
        throw new Error(messages.canvasUnavailable);
      }

      canvas.width = Math.max(1, Math.ceil(viewport.width));
      canvas.height = Math.max(1, Math.ceil(viewport.height));
      await page.render({ canvasContext: context, viewport }).promise;
      thumbnails.push({
        pageNumber,
        dataUrl: canvas.toDataURL("image/jpeg", 0.72),
      });
      page.cleanup();
      canvas.width = 0;
      canvas.height = 0;
      onProgress(pageNumber, documentProxy.numPages);
      await new Promise<void>((resolve) => {
        window.requestAnimationFrame(() => resolve());
      });
    }
    return thumbnails;
  } finally {
    signal.removeEventListener("abort", cancelLoading);
    if (documentProxy) {
      await documentProxy.destroy();
    } else {
      await loadingTask.destroy();
    }
  }
}
