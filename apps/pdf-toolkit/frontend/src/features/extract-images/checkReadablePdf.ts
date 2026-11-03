import {
  GlobalWorkerOptions,
  getDocument,
  type PDFDocumentProxy,
} from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

type ReadabilityMessages = {
  unreadablePdf: string;
  noTextLayer: string;
};

export async function checkReadablePdf(
  file: File,
  messages: ReadabilityMessages,
  signal?: AbortSignal,
): Promise<void> {
  const noTextError = new Error(messages.noTextLayer);
  let loadingTask: ReturnType<typeof getDocument> | null = null;
  let documentProxy: PDFDocumentProxy | null = null;

  const release = () => {
    const currentDocument = documentProxy;
    const currentTask = loadingTask;
    documentProxy = null;
    loadingTask = null;
    const cleanup = currentDocument ? currentDocument.destroy() : currentTask?.destroy();
    void cleanup?.catch((reason: unknown) => {
      console.error("Unable to release the PDF readability check:", reason);
    });
  };
  const abortInspection = () => release();

  if (signal?.aborted) throw new Error("PDF readability check was aborted");
  signal?.addEventListener("abort", abortInspection, { once: true });

  try {
    const data = new Uint8Array(await file.arrayBuffer());
    if (signal?.aborted) throw new Error("PDF readability check was aborted");

    loadingTask = getDocument({ data });
    documentProxy = await loadingTask.promise;
    if (signal?.aborted) throw new Error("PDF readability check was aborted");
    if (documentProxy.numPages < 1) throw new Error(messages.unreadablePdf);

    let hasText = false;
    for (let pageNumber = 1; pageNumber <= documentProxy.numPages; pageNumber++) {
      if (signal?.aborted) throw new Error("PDF readability check was aborted");
      const page = await documentProxy.getPage(pageNumber);
      try {
        const content = await page.getTextContent();
        if (
          content.items.some(
            (item) => "str" in item && typeof item.str === "string" && item.str.trim().length > 0,
          )
        ) {
          hasText = true;
          break;
        }
      } finally {
        page.cleanup();
      }
    }

    if (!hasText) throw noTextError;
  } catch (reason: unknown) {
    if (signal?.aborted) throw reason;
    if (reason === noTextError) throw noTextError;
    throw new Error(messages.unreadablePdf);
  } finally {
    signal?.removeEventListener("abort", abortInspection);
    release();
  }
}
