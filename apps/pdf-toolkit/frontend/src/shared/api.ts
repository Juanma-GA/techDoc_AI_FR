import type { TFunction } from "i18next";

const API_BASE = `${import.meta.env.BASE_URL.replace(/\/$/, "")}/api/v1`;

type ErrorPayload = {
  error?: unknown;
};

export async function processPDF(
  endpoint:
    | "merge"
    | "images-to-pdf"
    | "compress"
    | "extract"
    | "delete"
    | "reorder"
    | "rotate"
    | "signature",
  data: FormData,
  downloadName: string,
  t: TFunction,
): Promise<void> {
  await downloadFromApi(endpoint, data, downloadName, "application/pdf", t);
}

export async function processSplit(data: FormData, downloadName: string, t: TFunction): Promise<void> {
  await downloadFromApi("split", data, downloadName, "application/zip", t);
}

async function downloadFromApi(
  endpoint: string,
  data: FormData,
  downloadName: string,
  expectedType: string,
  t: TFunction,
): Promise<void> {
  const response = await fetch(`${API_BASE}/${endpoint}`, {
    method: "POST",
    body: data,
  });
  if (!response.ok) {
    const message = await responseError(response);
    throw new Error(
      message ? translateApiError(message, t) : t("apiErrors.requestFailed", { status: response.status }),
    );
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes(expectedType)) {
    throw new Error(t("apiErrors.invalidResponse"));
  }

  const blob = await response.blob();
  if (blob.size === 0) {
    throw new Error(t("apiErrors.emptyPdf"));
  }

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = downloadName;
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
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
    "Chaque fichier PDF doit faire au maximum 250 Mo.": "apiErrors.fileTooLarge",
    "Chaque fichier doit faire au maximum 250 Mo.": "apiErrors.fileTooLarge",
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
