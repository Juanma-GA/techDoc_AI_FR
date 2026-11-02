import type { TFunction } from "i18next";

import type { ExportProgressHandler } from "../../shared/api";

const API_BASE = `${import.meta.env.BASE_URL.replace(/\/$/, "")}/api/v1`;
const noImagesError = "Le PDF ne contient aucune image à extraire.";

export function extractImagesFromPDF(
  file: File,
  t: TFunction,
  onProgress: ExportProgressHandler,
  signal?: AbortSignal,
): Promise<Blob> {
  const data = new FormData();
  data.append("file", file, file.name);

  return new Promise<Blob>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE}/extract-images`);
    request.responseType = "blob";
    if (signal?.aborted) {
      reject(new Error(t("extractImages.failed")));
      return;
    }

    const cleanup = () => signal?.removeEventListener("abort", abortRequest);
    const abortRequest = () => request.abort();
    signal?.addEventListener("abort", abortRequest, { once: true });
    onProgress({ phase: "uploading", percentage: 0 });

    request.upload.onprogress = (event) => {
      onProgress({
        phase: "uploading",
        percentage: event.lengthComputable ? progressPercentage(event.loaded, event.total) : null,
      });
    };
    request.upload.onload = () => {
      onProgress({ phase: "processing", percentage: null });
    };
    request.onprogress = (event) => {
      const contentType = request.getResponseHeader("content-type") ?? "";
      if (request.status >= 200 && request.status < 300 && contentType.includes("application/zip")) {
        onProgress({
          phase: "downloading",
          percentage: event.lengthComputable ? progressPercentage(event.loaded, event.total) : null,
        });
      }
    };
    request.onerror = () => {
      cleanup();
      reject(new TypeError(t("apiErrors.networkError")));
    };
    request.onabort = () => {
      cleanup();
      reject(new Error(t("extractImages.failed")));
    };
    request.onload = () => {
      cleanup();
      void handleResponse().then(resolve, reject);
    };
    try {
      request.send(data);
    } catch (reason: unknown) {
      cleanup();
      reject(reason);
    }

    async function handleResponse(): Promise<Blob> {
      const response = request.response;
      if (!(response instanceof Blob)) {
        throw new Error(t("extractImages.invalidArchive"));
      }
      if (request.status < 200 || request.status >= 300) {
        throw new Error(await responseError(response, t));
      }
      if (!(request.getResponseHeader("content-type") ?? "").includes("application/zip")) {
        throw new Error(t("extractImages.invalidArchive"));
      }
      if (response.size === 0) {
        throw new Error(t("extractImages.emptyArchive"));
      }
      onProgress({ phase: "downloading", percentage: 100 });
      return response;
    }
  });
}

async function responseError(response: Blob, t: TFunction): Promise<string> {
  let payload: unknown;
  try {
    payload = JSON.parse(await response.text());
  } catch {
    return t("extractImages.failed");
  }
  if (
    typeof payload === "object" &&
    payload !== null &&
    "error" in payload &&
    payload.error === noImagesError
  ) {
    return t("extractImages.noImagesFound");
  }
  return t("extractImages.failed");
}

function progressPercentage(loaded: number, total: number): number {
  return total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0;
}
