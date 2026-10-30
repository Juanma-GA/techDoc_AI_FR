import { API_BASE, apiBlob, request, apiValidated, decodeResponse, ApiRequestError, responseId } from "./client";
import { parseWizardState, parsePmcResult } from "../wizardSchema";
import { generatedValidationBatchSchema } from "../validationSchema";
import { z } from "zod";
import type { WizardState } from "../wizardTypes";
import { readApiSse } from "./sse";

export const wizardApi = {
  thumbnailUrl: (docId: string, name: string, size = 192) =>
    `${API_BASE}/documents/${docId}/wizard/images/${encodeURIComponent(name)}/thumb?size=${size}`,
  validate: (docId: string, dmIds?: string[]) =>
    apiValidated(
      `/documents/${docId}/wizard/validate`,
      (value) => generatedValidationBatchSchema.parse(value),
      { method: "POST", body: JSON.stringify({ dm_ids: dmIds ?? null }) },
    ),
  get: (docId: string) => apiValidated(`/documents/${docId}/wizard`, parseWizardState),
  // action : "update" | "advance" | "back" (+ params optionnels).
  action: (docId: string, action: string, params?: Record<string, unknown>) =>
    apiValidated(`/documents/${docId}/wizard/${action}`, parseWizardState, {
      method: "POST",
      ...(params ? { body: JSON.stringify(params) } : {}),
    }),
  dmXmlUrl: (docId: string, dmId: string) =>
    `${API_BASE}/documents/${docId}/wizard/dm/${dmId}/xml`,
  downloadDmFile: async (docId: string, dmId: string): Promise<File> => {
    return apiBlob(`/documents/${encodeURIComponent(docId)}/wizard/dm/${encodeURIComponent(dmId)}/xml`,
      `${dmId}.xml`);
  },
  zipUrl: (
    docId: string,
    options: {
      maxDimension?: number;
      format?: "original" | "jpeg" | "png";
    } = {},
  ) => {
    const params = new URLSearchParams();
    if (options.maxDimension !== undefined) {
      params.set("max_dimension", String(options.maxDimension));
    }
    if (options.format && options.format !== "original") {
      params.set("image_format", options.format);
    }
    const query = params.toString();
    return `${API_BASE}/documents/${docId}/wizard/zip${query ? `?${query}` : ""}`;
  },
  images: (docId: string) => apiValidated(`/documents/${docId}/wizard/images`, (value) => z.array(z.string()).parse(value)),
  imageUrl: (docId: string, name: string) =>
    `${API_BASE}/documents/${docId}/wizard/images/${encodeURIComponent(name)}`,
};


/**
 * Lance la generation et consomme le flux SSE (fetch +
 * ReadableStream ; EventSource ne sait pas POST). `onEvent(event, data)`.
 */
export async function startWizardStream(
  docId: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<WizardState> {
  const res = await request(`/documents/${docId}/wizard/start_stream`, {
    method: "POST",
    signal,
  });
  let completed: WizardState | undefined;
  await readApiSse(res, (event, data) => {
    if (event === "error") throw new ApiRequestError(res.status,
      typeof data.code === "string" ? data.code : "START_FAILED",
      typeof data.message === "string" ? data.message : "Stream failed.", responseId(res));
    if (event === "done") {
      completed = decodeResponse(res, parseWizardState, data);
      onEvent(event, { ...completed });
    } else onEvent(event, data);
  }, signal);
  if (!completed) throw new ApiRequestError(res.status, "INCOMPLETE_STREAM",
    "Stream ended without a completion event.", responseId(res));
  return completed;
}


export async function generatePmcStream(
  docId: string,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await request(`/documents/${docId}/validate-and-generate-pmc`, {
    method: "POST", signal,
  });
  let completed = false;
  await readApiSse(res, (event, data) => {
    if (event === "error") throw new ApiRequestError(res.status,
      typeof data.code === "string" ? data.code : "PMC_GENERATION_FAILED",
      typeof data.message === "string" ? data.message : "Stream failed.", responseId(res));
    if (event === "done") {
      completed = true;
      onEvent(event, decodeResponse(res, parsePmcResult, data));
    } else onEvent(event, data);
  }, signal);
  if (!completed) throw new ApiRequestError(res.status, "INCOMPLETE_STREAM",
    "Stream ended without a completion event.", responseId(res));
}
