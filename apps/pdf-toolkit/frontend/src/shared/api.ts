import { isTauri } from "@tauri-apps/api/core";
import type { TFunction } from "i18next";
import { save } from "@tauri-apps/plugin-dialog";

import type { PDFEndpoint } from "./pdfEndpoints";

const API_BASE = `${import.meta.env.BASE_URL.replace(/\/$/, "")}/api/v1`;

type ErrorPayload = {
  error?: unknown;
};

export type ExportProgressState = {
  phase:
    | "uploading"
    | "processing"
    | "downloading"
    | "preparing"
    | "pages"
    | "splitFiles"
    | "splitArchive"
    | "progressUnavailable";
  percentage: number | null;
  completed?: number;
  total?: number;
};

export type ExportProgressHandler = (progress: ExportProgressState) => void;

type SplitProgressResponse = {
  phase: "processing" | "extracting" | "archiving";
  completed: number;
  total: number;
};

type ExportWritableFile = {
  write: (data: Blob) => Promise<void>;
  close: () => Promise<void>;
};

export type ExportDestination = {
  name: string;
  createWritable: () => Promise<ExportWritableFile>;
};

export type SplitDestination =
  | { kind: "browser"; file: ExportDestination | undefined }
  | { kind: "tauri"; zipPath: string };

type SaveFilePickerWindow = Window & {
  showSaveFilePicker?: (options: { suggestedName: string }) => Promise<ExportDestination>;
};

export function validateExportFileName(name: string): "required" | "invalidName" | null {
  const trimmedName = name.trim();
  if (!trimmedName) {
    return "required";
  }
  if (
    /[<>:"/\\|?*\u0000-\u001f]/u.test(trimmedName) ||
    /[. ]$/u.test(trimmedName) ||
    /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$/iu.test(trimmedName)
  ) {
    return "invalidName";
  }
  return null;
}

export async function chooseExportDestination(
  suggestedName: string,
  t: TFunction,
): Promise<ExportDestination | null | undefined> {
  if (typeof window === "undefined") {
    return undefined;
  }
  const browserWindow = window as SaveFilePickerWindow;
  if (!browserWindow.showSaveFilePicker) {
    return undefined;
  }
  try {
    return await browserWindow.showSaveFilePicker({ suggestedName });
  } catch (reason) {
    if (reason instanceof DOMException && reason.name === "AbortError") {
      return null;
    }
    throw new Error(t("exportOptions.savePickerFailed"));
  }
}

export async function chooseSplitDestination(
  suggestedName: string,
  t: TFunction,
): Promise<SplitDestination | null> {
  if (isTauri()) {
    try {
      const zipPath = await save({
        defaultPath: suggestedName,
        filters: [{ name: "ZIP archive", extensions: ["zip"] }],
      });
      return zipPath ? { kind: "tauri", zipPath } : null;
    } catch (reason) {
      const detail = reason instanceof Error ? reason.message : String(reason);
      throw new Error(`${t("exportOptions.savePickerFailed")} (${detail})`);
    }
  }

  const file = await chooseExportDestination(suggestedName, t);
  return file === null ? null : { kind: "browser", file };
}

export async function processPDF(
  endpoint: PDFEndpoint,
  data: FormData,
  downloadName: string,
  t: TFunction,
  onProgress?: ExportProgressHandler,
  destination?: ExportDestination,
): Promise<string> {
  return downloadFromApi(endpoint, data, downloadName, "application/pdf", t, onProgress, destination);
}

export async function processSplit(
  data: FormData,
  downloadName: string,
  t: TFunction,
  onProgress?: ExportProgressHandler,
  destination?: SplitDestination,
): Promise<string> {
  const directSplitExport = destination?.kind === "tauri";
  const fileDestination = destination?.kind === "browser" ? destination.file : undefined;
  if (directSplitExport) {
    data.append("zip_path", destination.zipPath);
  }
  return downloadFromApi(
    "split",
    data,
    downloadName,
    directSplitExport ? "application/json" : "application/zip",
    t,
    onProgress,
    fileDestination,
    crypto.randomUUID(),
    directSplitExport,
  );
}

function downloadFromApi(
  endpoint: string,
  data: FormData,
  downloadName: string,
  expectedType: string,
  t: TFunction,
  onProgress?: ExportProgressHandler,
  destination?: ExportDestination,
  splitProgressId?: string,
  directSplitExport = false,
): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE}/${endpoint}`);
    request.responseType = "blob";
    if (splitProgressId) {
      request.setRequestHeader("X-Split-Progress-ID", splitProgressId);
    }
    if (directSplitExport) {
      request.setRequestHeader("X-PDF-Toolkit-Direct-Export", "1");
    }
    onProgress?.({ phase: "uploading", percentage: 0 });

    let progressPollingStopped = false;
    let progressTimer: number | undefined;
    let progressController: AbortController | undefined;
    let progressFailureShown = false;

    const stopProgressPolling = () => {
      progressPollingStopped = true;
      if (progressTimer !== undefined) {
        window.clearTimeout(progressTimer);
      }
      progressController?.abort();
    };

    const pollSplitProgress = async (): Promise<void> => {
      if (!splitProgressId || progressPollingStopped || progressController) {
        return;
      }
      const controller = new AbortController();
      progressController = controller;
      try {
        const response = await fetch(
          `${API_BASE}/split/progress/${encodeURIComponent(splitProgressId)}`,
          { cache: "no-store", signal: controller.signal },
        );
        if (!response.ok) {
          throw new Error(`Progress request failed with status ${response.status}`);
        }
        const payload: unknown = await response.json();
        if (!isSplitProgressResponse(payload)) {
          throw new Error("Invalid split progress response");
        }
        progressFailureShown = false;
        if (payload.phase === "processing" || payload.total === 0) {
          onProgress?.({ phase: "processing", percentage: null });
        } else {
          const phase = payload.phase === "extracting" ? "splitFiles" : "splitArchive";
          onProgress?.({
            phase,
            percentage: progressPercentage(payload.completed, payload.total),
            completed: payload.completed,
            total: payload.total,
          });
        }
      } catch (reason) {
        if (!controller.signal.aborted && !progressFailureShown) {
          onProgress?.({ phase: "progressUnavailable", percentage: null });
          progressFailureShown = true;
        }
      } finally {
        progressController = undefined;
        if (!progressPollingStopped) {
          progressTimer = window.setTimeout(() => void pollSplitProgress(), 500);
        }
      }
    };

    request.upload.onprogress = (event) => {
      onProgress?.({
        phase: "uploading",
        percentage: event.lengthComputable ? progressPercentage(event.loaded, event.total) : null,
      });
    };
    request.upload.onload = () => {
      onProgress?.({ phase: "processing", percentage: null });
      void pollSplitProgress();
    };
    request.onreadystatechange = () => {
      if (request.readyState !== XMLHttpRequest.HEADERS_RECEIVED) {
        return;
      }
      stopProgressPolling();
      const contentType = request.getResponseHeader("content-type") ?? "";
      if (request.status >= 200 && request.status < 300 && contentType.includes(expectedType)) {
        onProgress?.({ phase: "downloading", percentage: 0 });
      }
    };
    request.onprogress = (event) => {
      const contentType = request.getResponseHeader("content-type") ?? "";
      if (request.status >= 200 && request.status < 300 && contentType.includes(expectedType)) {
        onProgress?.({
          phase: "downloading",
          percentage: event.lengthComputable ? progressPercentage(event.loaded, event.total) : null,
        });
      }
    };
    request.onload = () => {
      stopProgressPolling();
      void handleResponse().catch(reject);
    };
    request.onerror = () => {
      stopProgressPolling();
      reject(new TypeError("Network request failed"));
    };
    request.onabort = () => {
      stopProgressPolling();
      reject(new Error(t("apiErrors.requestFailed", { status: request.status })));
    };

    async function handleResponse(): Promise<void> {
      const blob = request.response;
      if (!(blob instanceof Blob)) {
        reject(new Error(t("apiErrors.invalidResponse")));
        return;
      }
      if (request.status < 200 || request.status >= 300) {
        const message = await responseError(blob, request.getResponseHeader("content-type") ?? "");
        reject(
          new Error(
            message
              ? translateApiError(message, t)
              : t("apiErrors.requestFailed", { status: request.status }),
          ),
        );
        return;
      }

      const contentType = request.getResponseHeader("content-type") ?? "";
      if (!contentType.includes(expectedType)) {
        reject(new Error(t("apiErrors.invalidResponse")));
        return;
      }
      if (blob.size === 0) {
        reject(new Error(t("apiErrors.emptyPdf")));
        return;
      }

      if (directSplitExport) {
        let payload: unknown;
        try {
          payload = JSON.parse(await blob.text());
        } catch {
          reject(new Error(t("apiErrors.invalidResponse")));
          return;
        }
        if (!isDirectSplitResponse(payload)) {
          reject(new Error(t("apiErrors.invalidResponse")));
          return;
        }
        resolve(payload.file_name);
        return;
      }

      resolve(await saveExportBlob(blob, downloadName, destination, t));
    }

    request.send(data);
  });
}

function isDirectSplitResponse(value: unknown): value is { file_name: string } {
  return (
    typeof value === "object" &&
    value !== null &&
    "file_name" in value &&
    typeof value.file_name === "string" &&
    value.file_name.length > 0
  );
}

function isSplitProgressResponse(value: unknown): value is SplitProgressResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "phase" in value &&
    (value.phase === "processing" || value.phase === "extracting" || value.phase === "archiving") &&
    "completed" in value &&
    typeof value.completed === "number" &&
    Number.isInteger(value.completed) &&
    "total" in value &&
    typeof value.total === "number" &&
    Number.isInteger(value.total) &&
    value.completed >= 0 &&
    value.total >= value.completed
  );
}

function progressPercentage(loaded: number, total: number): number {
  return total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0;
}

function downloadBlob(blob: Blob, downloadName: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = downloadName;
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function saveExportBlob(
  blob: Blob,
  downloadName: string,
  destination: ExportDestination | undefined,
  t: TFunction,
): Promise<string> {
  if (!destination) {
    downloadBlob(blob, downloadName);
    return downloadName;
  }

  try {
    const writable = await destination.createWritable();
    await writable.write(blob);
    await writable.close();
    return destination.name;
  } catch (reason) {
    if (reason instanceof Error) {
      throw new Error(`${t("exportOptions.saveFailed")} ${reason.message}`);
    }
    throw new Error(t("exportOptions.saveFailed"));
  }
}

export function formatOperationError(
  reason: unknown,
  t: TFunction,
  fallbackKey: string,
): string {
  if (reason instanceof TypeError) {
    return t("apiErrors.networkError");
  }
  if (reason instanceof Error) {
    return reason.message;
  }
  return t(fallbackKey);
}

function translateApiError(message: string, t: TFunction): string {
  const messageKeys: Record<string, string> = {
    "La requête doit être un formulaire multipart.": "apiErrors.multipartRequired",
    "Le formulaire envoyé est incomplet ou invalide.": "apiErrors.invalidMultipart",
    "Un champ du formulaire est invalide.": "apiErrors.invalidField",
    "Le formulaire contient un champ inattendu.": "apiErrors.unexpectedField",
    "Un champ du formulaire est trop volumineux.": "apiErrors.fieldTooLarge",
    "Le formulaire contient un fichier inattendu.": "apiErrors.unexpectedFile",
    "Un seul fichier PDF est accepté pour cette opération.": "apiErrors.singleFileOnly",
    "Chaque fichier PDF doit faire au maximum 500 Mo.": "apiErrors.fileTooLarge",
    "Chaque fichier doit faire au maximum 500 Mo.": "apiErrors.fileTooLarge",
    "Sélectionnez au moins deux fichiers PDF.": "apiErrors.mergeMinimumFiles",
    "Sélectionnez au moins une image PNG ou JPEG.": "apiErrors.selectImages",
    "Sélectionnez un fichier PDF.": "apiErrors.selectFile",
    "L'ordre des pages est invalide.": "apiErrors.invalidOrder",
    "Impossible de créer l'espace temporaire de traitement.": "apiErrors.workspaceFailed",
    "Impossible de lire le PDF traité.": "apiErrors.readFailed",
    "Vérifiez les pages et les fichiers sélectionnés.": "apiErrors.invalidSelection",
    "Vérifiez les options et le PDF sélectionnés.": "apiErrors.invalidSelection",
    "L'angle de rotation est invalide.": "apiErrors.invalidRotation",
    "Le fichier fourni est invalide ou ne peut pas être traité.": "apiErrors.invalidDocument",
    "Le traitement du PDF a échoué.": "apiErrors.processingFailed",
    "Impossible de préparer les fichiers PDF.": "apiErrors.prepareFailed",
    "L'image de signature dépasse la limite de 10 Mo.": "signature.apiImageTooLarge",
    "Le nom ou la date contient un caractère que le PDF ne peut pas afficher.": "signature.unsupportedText",
    "La liste des documents à générer est invalide.": "split.apiInvalidGroups",
    "Le découpage dépasse le nombre maximal de documents.": "split.apiTooManyGroups",
  };
  const key = messageKeys[message];
  if (key) {
    return t(key);
  }

  const requiredField = /^Le champ « (.+) » est requis\.$/.exec(message);
  if (requiredField) {
    return t("apiErrors.fieldRequired", { field: requiredField[1] });
  }

  const invalidFile = /^« (.+) » n'est pas un fichier PDF valide\.$/.exec(message);
  if (invalidFile) {
    return t("apiErrors.invalidPdfFile", { name: invalidFile[1] });
  }

  const invalidImage = /^« (.+) » n'est pas une image PNG ou JPEG valide\.$/.exec(message);
  if (invalidImage) {
    return t("apiErrors.invalidImage", { name: invalidImage[1] });
  }

  return message;
}

async function responseError(blob: Blob, contentType: string): Promise<string | null> {
  const body = await blob.text();
  if (!body) {
    return null;
  }
  if (!contentType.includes("application/json")) {
    return body;
  }

  let payload: ErrorPayload;
  try {
    payload = JSON.parse(body) as ErrorPayload;
  } catch (error) {
    if (error instanceof SyntaxError) {
      return body;
    }
    throw error;
  }
  return typeof payload.error === "string" ? payload.error : body;
}
