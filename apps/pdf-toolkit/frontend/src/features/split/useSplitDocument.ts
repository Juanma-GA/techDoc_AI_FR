import { useEffect, useState } from "react";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

import { readSplitBookmarks, type SplitBookmark } from "./bookmarkSplit";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

const emptyDocument = {
  pageCount: 0,
  bookmarks: [] as SplitBookmark[],
  skipped: 0,
  loading: false,
  error: "",
};

export function useSplitDocument(file: File | null) {
  const [state, setState] = useState({ ...emptyDocument, file });
  useEffect(() => {
    let active = true;
    let task: ReturnType<typeof getDocument> | null = null;
    const release = () => {
      const currentTask = task;
      task = null;
      if (currentTask) void currentTask.destroy().catch(() => {
        if (active) setState({ ...emptyDocument, file, error: "split.documentFailed" });
      });
    };
    setState({ ...emptyDocument, file, loading: Boolean(file) });
    if (!file) return;
    void (async () => {
      try {
        const buffer = await file.arrayBuffer();
        if (!active) return;
        task = getDocument({ data: new Uint8Array(buffer) });
        const document = await task.promise;
        if (!active) return;
        let bookmarkData = { bookmarks: [] as SplitBookmark[], skipped: 0 };
        let error = "";
        try {
          bookmarkData = await readSplitBookmarks(document);
        } catch {
          error = "split.bookmarksFailed";
        }
        if (active) setState({
          file, pageCount: document.numPages, ...bookmarkData, error, loading: false,
        });
      } catch {
        if (active) setState({ ...emptyDocument, file, error: "split.documentFailed" });
      } finally {
        release();
      }
    })();
    return () => {
      active = false;
      release();
    };
  }, [file]);
  return state.file === file ? state : { ...emptyDocument, loading: Boolean(file) };
}
