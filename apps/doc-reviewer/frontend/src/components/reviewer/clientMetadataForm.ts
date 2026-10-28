import type { ClientMappingField } from "../../hooks/useClientConfig";
import type { Document } from "../../types/domain";

export type ClientMetadataDraft = Record<string, unknown>;

const LEGACY_METADATA: Record<string, string> = {
  meta_revision_date: "meta_revision_date",
  meta_cmm_number: "meta_cmm_number",
  meta_first_issue_date: "meta_first_issue_date",
  meta_last_issue_date: "meta_last_issue_date",
  meta_revision_number: "meta_revision_number",
  meta_pnr_number: "meta_pnr_number",
  meta_manufacturer: "meta_manufacturer",
  document_language: "document_language",
};

export function createClientMetadataDraft(
  document: Document,
  fields: Record<string, ClientMappingField>,
  mappingValues?: Record<string, unknown>,
): ClientMetadataDraft {
  const metadata = mappingValues ?? document.client_metadata ?? {};
  const legacyDocument = document as unknown as Record<string, unknown>;
  return Object.fromEntries(
    Object.entries(fields).map(([name, definition]) => {
      const legacyField = LEGACY_METADATA[name];
      const value = Object.prototype.hasOwnProperty.call(metadata, name)
        ? metadata[name]
        : mappingValues === undefined
          ? (legacyField ? legacyDocument[legacyField] : undefined) ?? definition.default
          : definition.default;
      if (definition.type === "string_list") {
        if (Array.isArray(value)) return [name, value.map(String)];
        return [name, typeof value === "string" && value.trim() ? [value.trim()] : []];
      }
      if (definition.type === "boolean") return [name, value === true];
      return [name, value === null || value === undefined ? "" : String(value)];
    }),
  );
}

export function hasClientMetadataValue(value: unknown): boolean {
  if (Array.isArray(value)) return value.some((item) => String(item ?? "").trim());
  if (typeof value === "boolean" || typeof value === "number") return true;
  return String(value ?? "").trim().length > 0;
}

export function matchesClientMetadataPattern(
  value: unknown,
  definition: ClientMappingField,
): boolean {
  if (!definition.pattern || !hasClientMetadataValue(value)) return true;
  const candidates = definition.type === "string_list" && Array.isArray(value)
    ? value
    : [value];
  try {
    const pattern = new RegExp(`^(?:${definition.pattern})$`);
    return candidates.every((item) => pattern.test(String(item ?? "").trim()));
  } catch {
    return true;
  }
}

export function serializeClientMetadataValue(
  value: unknown,
  definition: ClientMappingField,
): unknown {
  if (definition.type === "string_list") {
    return Array.isArray(value)
      ? value.map((item) => String(item).trim()).filter(Boolean)
      : [];
  }
  if (definition.type === "boolean") return value === true;
  if (definition.type === "integer" || definition.type === "number") {
    const text = String(value ?? "").trim();
    if (!text) return null;
    const parsed = Number(text);
    return Number.isFinite(parsed)
      ? definition.type === "integer" ? Math.trunc(parsed) : parsed
      : null;
  }
  const text = String(value ?? "").trim();
  return text || null;
}
