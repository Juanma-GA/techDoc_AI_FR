import { useEffect, useState } from "react";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

type PageCountState = { file: File | null; pageCount: number; loading: boolean; failed: boolean };

export function usePdfPageCount(file: File | null) {
  const [state, setState] = useState<PageCountState>({
    file, pageCount: 0, loading: Boolean(file), failed: false,
  });
  useEffect(() => {
    let active = true;
    let task: ReturnType<typeof getDocument> | null = null;
    const release = () => {
      const currentTask = task;
      task = null;
      if (currentTask) void currentTask.destroy().catch(() => undefined);
    };
    setState({ file, pageCount: 0, loading: Boolean(file), failed: false });
    if (!file) return;
    void (async () => {
      try {
        const buffer = await file.arrayBuffer();
        if (!active) return;
        task = getDocument({ data: new Uint8Array(buffer) });
        const document = await task.promise;
        if (active) setState({ file, pageCount: document.numPages, loading: false, failed: false });
      } catch {
        if (active) setState({ file, pageCount: 0, loading: false, failed: true });
      } finally {
        release();
      }
    })();
    return () => {
      active = false;
      release();
    };
  }, [file]);
  return state.file === file
    ? state
    : { file, pageCount: 0, loading: Boolean(file), failed: false };
}
