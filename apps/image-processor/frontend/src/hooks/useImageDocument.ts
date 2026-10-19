import type { TFunction } from "i18next";
import { useEffect, useMemo, useState } from "react";

import type { OcrResultDto } from "../lib/api";
import { MAX_UPLOAD_BYTES } from "../lib/image-processing";
import { restoreFile, type ImageRevision, type Operation, type WorkspaceSnapshot } from "../lib/workspace-api";

const SUPPORTED_TYPES = new Set([
  "image/png", "image/jpeg", "image/webp", "image/bmp", "image/tiff", "image/x-tiff",
]);
type DocumentState = {
  id: string;
  source: File;
  revisions: ImageRevision[];
  operations: Operation[];
};

export function useImageDocument(t: TFunction) {
  const [document, setDocument] = useState<DocumentState | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const source = document?.source;
  const revision = document?.revisions.at(-1);
  const currentFile = useMemo(
    () => revision ? restoreFile(revision.image) : source ?? null,
    [revision, source],
  );
  const result = useMemo<OcrResultDto | null>(
    () => revision?.analysis
      ? { ...revision.analysis, edited_image: revision.image.data_url }
      : null,
    [revision],
  );

  useEffect(() => {
    if (!source) {
      setSourceUrl("");
      return;
    }
    const url = URL.createObjectURL(source);
    setSourceUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [source]);

  function chooseImage(files: File[]) {
    const file = files[0];
    if (!file) return false;
    if (!SUPPORTED_TYPES.has(file.type)) throw new Error(t("image.errorImageType"));
    if (file.size > MAX_UPLOAD_BYTES) throw new Error(t("image.errorImageSize"));
    setDocument({ id: crypto.randomUUID(), source: file, revisions: [], operations: [] });
    return true;
  }

  function appendRevision(next: ImageRevision) {
    setDocument((current) => current && current.id === document?.id ? {
      ...current,
      revisions: [...current.revisions, next],
      operations: [...current.operations, { kind: next.kind, at: new Date().toISOString() }],
    } : current);
  }

  function applyOcr(payload: OcrResultDto) {
    const { edited_image, ...analysis } = payload;
    appendRevision({
      kind: "ocr",
      image: { name: payload.filename, data_url: edited_image },
      analysis,
    });
  }

  function applyTextReplacement(payload: OcrResultDto) {
    const { edited_image, ...analysis } = payload;
    appendRevision({
      kind: "text-replacement",
      image: { name: payload.filename, data_url: edited_image },
      analysis,
    });
  }

  function applyBrush(image: string, mode: "lama" | "color") {
    const extension = image.startsWith("data:image/jpeg") ? "jpg" : "png";
    const baseName = revision?.analysis?.filename ?? currentFile?.name ?? "image";
    const name = `${baseName.replace(/\.[^.]+$/, "")}.${extension}`;
    appendRevision({
      kind: `brush-${mode}`,
      image: { name, data_url: image },
      analysis: revision?.analysis ?? null,
    });
  }

  function undo() {
    setDocument((current) => current && current.revisions.length > 0 ? {
      ...current,
      revisions: current.revisions.slice(0, -1),
      operations: [...current.operations, { kind: "undo", at: new Date().toISOString() }],
    } : current);
  }

  function restore(id: string, snapshot: WorkspaceSnapshot) {
    setDocument({
      id, source: restoreFile(snapshot.image),
      revisions: snapshot.revisions, operations: snapshot.operations,
    });
  }

  return {
    document, currentFile, result,
    imageFile: source ?? null,
    imageUrl: revision?.image.data_url || sourceUrl,
    manuallyEdited: Boolean(revision?.kind.startsWith("brush-")),
    canUndo: Boolean(document?.revisions.length),
    chooseImage, applyOcr, applyTextReplacement, applyBrush, undo, restore,
    clear: () => setDocument(null),
  };
}
