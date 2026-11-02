import { useEffect, useState } from "react";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export type PDFMetadata = {
  title: string;
  author: string;
  subject: string;
  keywords: string;
};

const emptyMetadata: PDFMetadata = { title: "", author: "", subject: "", keywords: "" };
const fields = [
  ["title", "Title", "dc:title"],
  ["author", "Author", "dc:creator"],
  ["subject", "Subject", "dc:description"],
  ["keywords", "Keywords", "pdf:keywords"],
] as const;

type MetadataState = {
  file: File | null;
  values: PDFMetadata;
  loading: boolean;
  failed: boolean;
};

function metadataText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value) && value.every((item: unknown) => typeof item === "string")) {
    return value.join(", ");
  }
  throw new TypeError("PDF metadata contains an unsupported value");
}

export function usePdfMetadata(file: File | null) {
  const [state, setState] = useState<MetadataState>({
    file: null, values: emptyMetadata, loading: false, failed: false,
  });

  useEffect(() => {
    let active = true;
    let task: ReturnType<typeof getDocument> | null = null;
    const release = () => {
      const current = task;
      task = null;
      if (current) {
        void current.destroy().catch((reason: unknown) => {
          console.error("Unable to release the PDF metadata reader:", reason);
        });
      }
    };
    setState({ file, values: emptyMetadata, loading: Boolean(file), failed: false });
    if (!file) return;

    void (async () => {
      try {
        const buffer = await file.arrayBuffer();
        if (!active) return;
        task = getDocument({ data: new Uint8Array(buffer) });
        const document = await task.promise;
        const { info, metadata } = await document.getMetadata();
        if (!active) return;
        if (!info || typeof info !== "object") {
          throw new TypeError("PDF document properties are unavailable");
        }
        const values = { ...emptyMetadata };
        for (const [field, infoKey, xmpKey] of fields) {
          const infoValue: unknown = Reflect.get(info, infoKey);
          const xmpValue: unknown = metadata?.get(xmpKey);
          values[field] = metadataText(infoValue ?? xmpValue);
        }
        if (!values.keywords) {
          values.keywords = metadataText(metadata?.get("dc:subject"));
        }
        setState({ file, values, loading: false, failed: false });
      } catch (reason: unknown) {
        if (active) {
          console.error("Unable to read PDF metadata:", reason);
          setState({ file, values: emptyMetadata, loading: false, failed: true });
        }
      } finally {
        release();
      }
    })();
    return () => {
      active = false;
      release();
    };
  }, [file]);

  const current = state.file === file
    ? state
    : { file, values: emptyMetadata, loading: Boolean(file), failed: false };
  const update = (field: keyof PDFMetadata, value: string) => {
    setState((previous) => ({
      ...previous,
      values: { ...previous.values, [field]: value },
    }));
  };
  return { ...current, update };
}
