const API_BASE = `${import.meta.env.BASE_URL.replace(/\/$/, "")}/api/v1`;

type ErrorPayload = {
  error?: unknown;
};

export async function processPDF(
  endpoint: "merge" | "extract" | "delete" | "reorder",
  data: FormData,
  downloadName: string,
): Promise<void> {
  const response = await fetch(`${API_BASE}/${endpoint}`, {
    method: "POST",
    body: data,
  });
  if (!response.ok) {
    const message = await responseError(response);
    throw new Error(message || `Le traitement a échoué (${response.status}).`);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/pdf")) {
    throw new Error("Le serveur n'a pas renvoyé un fichier PDF.");
  }

  const blob = await response.blob();
  if (blob.size === 0) {
    throw new Error("Le fichier PDF généré est vide.");
  }

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = downloadName;
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function responseError(response: Response): Promise<string | null> {
  const body = await response.text();
  if (!body) {
    return null;
  }
  if (!response.headers.get("content-type")?.includes("application/json")) {
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
