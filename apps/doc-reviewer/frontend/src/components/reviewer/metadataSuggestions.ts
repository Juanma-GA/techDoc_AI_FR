import type { ClientMappingField } from "../../hooks/useClientConfig";
import type { DocumentMetadataSuggestions } from "../../hooks/useDocuments";

const SUGGESTED_FIELDS = [
  "meta_cmm_number",
  "meta_pnr_number",
  "meta_revision_number",
  "meta_revision_date",
  "meta_first_issue_date",
  "meta_update_type",
] as const;

const RESET_FIELD_DEFAULTS = {
  meta_manufacturer: "Airbus",
  document_language: "en",
} as const;

export function resetMappingWithSuggestions(
  fields: Record<string, ClientMappingField>,
  suggestions: DocumentMetadataSuggestions,
): Record<string, unknown> {
  const draft: Record<string, unknown> = Object.fromEntries(
    Object.entries(fields).map(([name, definition]) => [
      name,
      definition.type === "string_list"
        ? []
        : definition.type === "boolean"
          ? false
          : "",
    ]),
  );

  for (const [name, value] of Object.entries(RESET_FIELD_DEFAULTS)) {
    const definition = fields[name];
    if (
      definition?.type === "enum" &&
      definition.allowed_values?.includes(value)
    ) {
      draft[name] = value;
    }
  }

  for (const name of SUGGESTED_FIELDS) {
    const definition = fields[name];
    const value = suggestions[name];
    if (!definition || value === null || value === undefined || value === "") continue;
    if (definition.type === "enum" && !definition.allowed_values?.includes(String(value))) continue;

    if (Array.isArray(value)) {
      if (value.length === 0) continue;
      if (definition.type === "string_list") {
        draft[name] = value;
      } else if (definition.type === "string" || definition.type === "enum") {
        draft[name] = value.join(", ");
      }
    } else if (definition.type === "string" || definition.type === "enum") {
      draft[name] = value;
    }
  }

  return draft;
}
