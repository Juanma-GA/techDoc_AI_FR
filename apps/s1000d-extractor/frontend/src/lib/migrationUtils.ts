import type { TFunction } from "i18next";
import { ApiRequestError, type MigrationInputKind, type WizardDm } from "./api";

export function isRestorableMigrationInput(
  kind: MigrationInputKind,
): kind is "document" | "dmrl" | "dm_header" {
  return kind === "document" || kind === "dmrl" || kind === "dm_header";
}
export function generationFile(input: File | null, saved: File | null): File | null {
  return input ?? saved;
}
export function getCommonMissingFields(dms: readonly Pick<WizardDm, "missing_fields">[]): string[] {
  const first = dms[0];
  if (!first || dms.length < 2) return [];
  return [...new Set(first.missing_fields ?? [])]
    .filter((field) => dms.every((dm) => dm.missing_fields?.includes(field)));
}
export function formatApiError(t: TFunction, error: unknown): string {
  if (!(error instanceof ApiRequestError)) return error instanceof Error ? error.message : String(error);
  const message = t(`errors.${error.code}`, { defaultValue: error.message });
  return error.requestId && !message.includes(error.requestId)
    ? `${message} [${error.requestId}]` : message;
}
