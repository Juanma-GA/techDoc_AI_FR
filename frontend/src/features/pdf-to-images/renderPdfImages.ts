import { Zip, ZipPassThrough } from "fflate";
import { GlobalWorkerOptions, getDocument, type PDFDocumentProxy } from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export type RasterFormat = "png" | "jpeg";

export type PdfImageMessages = {
  emptyDocument: string;
  canvasUnavailable: string;
  renderFailed: string;
  archiveFailed: string;
};

export async function renderPdfImages(
  file: File,
  format: RasterFormat,
  onProgress: (completed: number, total: number) => void,
  signal: AbortSignal,
  messages: PdfImageMessages,
): Promise<Blob> {
  const data = new Uint8Array(await file.arrayBuffer());
  throwIfAborted(signal);

  const loadingTask = getDocument({ data });
  let documentProxy: PDFDocumentProxy | null = null;
  let cancelRender: (() => void) | null = null;
  const cancelLoading = () => {
    void loadingTask.destroy();
    cancelRender?.();
  };
  signal.addEventListener("abort", cancelLoading, { once: true });

  try {
    try {
      documentProxy = await loadingTask.promise;
    } catch {
      throw new Error(messages.renderFailed);
    }
    throwIfAborted(signal);
    if (documentProxy.numPages < 1) {
      throw new Error(messages.emptyDocument);
    }

    const zipParts: BlobPart[] = [];
    let archiveError = false;
    const archive = new Zip((error, chunk) => {
      if (error) {
        archiveError = true;
      } else {
        zipParts.push(chunk);
      }
    });
    onProgress(0, documentProxy.numPages);

    for (let pageNumber = 1; pageNumber <= documentProxy.numPages; pageNumber += 1) {
      throwIfAborted(signal);
      const page = await documentProxy.getPage(pageNumber);
      const naturalSize = page.getViewport({ scale: 1 });
      const scale = Math.min(2, 3000 / Math.max(naturalSize.width, naturalSize.height));
      const viewport = page.getViewport({ scale });
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d");
      if (!context) {
        throw new Error(messages.canvasUnavailable);
      }

      canvas.width = Math.max(1, Math.ceil(viewport.width));
      canvas.height = Math.max(1, Math.ceil(viewport.height));
      const renderTask = page.render({ canvasContext: context, viewport });
      cancelRender = () => renderTask.cancel();
      try {
        await renderTask.promise;
      } catch {
        if (signal.aborted) {
          throw new DOMException("Conversion cancelled", "AbortError");
        }
        throw new Error(messages.renderFailed);
      } finally {
        cancelRender = null;
      }

      const mimeType = format === "jpeg" ? "image/jpeg" : "image/png";
      const imageBlob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(
          (result) => {
            if (result) {
              resolve(result);
            } else {
              reject(new Error(messages.canvasUnavailable));
            }
          },
          mimeType,
          format === "jpeg" ? 0.92 : undefined,
        );
      });
      throwIfAborted(signal);

      const extension = format === "jpeg" ? "jpg" : "png";
      const entry = new ZipPassThrough(`page-${String(pageNumber).padStart(4, "0")}.${extension}`);
      archive.add(entry);
      entry.push(new Uint8Array(await imageBlob.arrayBuffer()), true);
      page.cleanup();
      canvas.width = 0;
      canvas.height = 0;
      onProgress(pageNumber, documentProxy.numPages);
      await new Promise<void>((resolve) => window.requestAnimationFrame(() => resolve()));
    }

    archive.end();
    if (archiveError) {
      throw new Error(messages.archiveFailed);
    }
    return new Blob(zipParts, { type: "application/zip" });
  } finally {
    signal.removeEventListener("abort", cancelLoading);
    if (documentProxy) {
      await documentProxy.destroy();
    } else {
      await loadingTask.destroy();
    }
  }
}

function throwIfAborted(signal: AbortSignal): void {
  if (signal.aborted) {
    throw new DOMException("Conversion cancelled", "AbortError");
  }
}
