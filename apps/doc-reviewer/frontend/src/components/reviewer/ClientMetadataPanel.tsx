import { AlertTriangle, CheckCircle2, Save, Settings2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useClientConfig } from "../../hooks/useClientConfig";
import { usePatchDocumentMeta } from "../../hooks/useDocuments";
import { missingDocumentContext } from "../../types/domain";
import type { Document } from "../../types/domain";
import type { ClientMappingField } from "../../hooks/useClientConfig";

type Props = {
  document: Document;
};

type Draft = Record<string, unknown>;

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

function createDraft(document: Document, fields: Record<string, ClientMappingField>): Draft {
  const metadata = document.client_metadata ?? {};
  const legacyDocument = document as unknown as Record<string, unknown>;
  return Object.fromEntries(
    Object.entries(fields).map(([name, definition]) => {
      const legacyField = LEGACY_METADATA[name];
      const value = Object.prototype.hasOwnProperty.call(metadata, name)
        ? metadata[name]
        : (legacyField ? legacyDocument[legacyField] : undefined) ?? definition.default;
      if (definition.type === "string_list") {
        if (Array.isArray(value)) return [name, value.map(String)];
        return [name, typeof value === "string" && value.trim() ? [value.trim()] : []];
      }
      if (definition.type === "boolean") return [name, value === true];
      return [name, value === null || value === undefined ? "" : String(value)];
    }),
  );
}

function hasValue(value: unknown): boolean {
  if (Array.isArray(value)) return value.some((item) => String(item ?? "").trim());
  if (typeof value === "boolean" || typeof value === "number") return true;
  return String(value ?? "").trim().length > 0;
}

function matchesPattern(value: unknown, definition: ClientMappingField): boolean {
  if (!definition.pattern || !hasValue(value)) return true;
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

function serializeValue(value: unknown, definition: ClientMappingField): unknown {
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

export function ClientMetadataPanel({ document }: Props) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language.toLowerCase().startsWith("en") ? "en" : "fr";
  const config = useClientConfig();
  const fields = config.data?.mapping.fields ?? {};
  const fieldEntries = Object.entries(fields);
  const requiredFields = fieldEntries
    .filter(([, definition]) => definition.required)
    .map(([name]) => name);
  const missingFields = config.data
    ? missingDocumentContext(document, requiredFields)
    : missingDocumentContext(document);
  const [draft, setDraft] = useState<Draft>(() => createDraft(document, fields));
  const [open, setOpen] = useState(missingFields.length > 0);
  const [saveState, setSaveState] = useState<"idle" | "saved" | "error">("idle");
  const patch = usePatchDocumentMeta(document.id);

  useEffect(() => {
    setDraft(createDraft(document, config.data?.mapping.fields ?? {}));
    setSaveState("idle");
  }, [document, config.data]);

  useEffect(() => {
    if (missingFields.length > 0) setOpen(true);
  }, [missingFields.length]);

  if (config.isLoading) {
    return <p className="hint">{t("common.loading")}</p>;
  }
  if (config.isError || !config.data) {
    return <p className="banner warn">{t("rules.client.loadFailed")}</p>;
  }

  const savedDraft = createDraft(document, fields);
  const dirty = JSON.stringify(draft) !== JSON.stringify(savedDraft);
  const draftComplete = requiredFields.every((field) => hasValue(draft[field]));
  const invalidFormatFields = new Set(
    fieldEntries
      .filter(([name, definition]) => !matchesPattern(draft[name], definition))
      .map(([name]) => name),
  );

  function updateField(name: string, value: unknown): void {
    setSaveState("idle");
    setDraft((current) => ({ ...current, [name]: value }));
  }

  function save(): void {
    if (invalidFormatFields.size > 0) return;
    const clientMetadata = Object.fromEntries(
      fieldEntries.map(([name, definition]) => [name, serializeValue(draft[name], definition)]),
    );
    setSaveState("idle");
    patch.mutate(
      { client_metadata: clientMetadata },
      {
        onSuccess: () => {
          setSaveState("saved");
          if (draftComplete) setOpen(false);
        },
        onError: () => setSaveState("error"),
      },
    );
  }

  if (!open) {
    return (
      <section className="document-meta-panel document-meta-panel--collapsed" aria-live="polite">
        <div className="document-meta-panel-summary">
          <div>
            <div className="document-meta-panel-title">{t("reviewer.meta.title")}</div>
            <span className="badge ok">
              <CheckCircle2 size={12} aria-hidden="true" />
              {t("reviewer.meta.statusReady")}
            </span>
          </div>
          <button type="button" className="btn ghost small" onClick={() => setOpen(true)}>
            <Settings2 size={14} />
            {t("reviewer.meta.edit")}
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="card document-meta-panel" aria-labelledby="document-meta-title">
      <div className="document-meta-panel-head">
        <div>
          <h2 id="document-meta-title" className="card-title">{t("reviewer.meta.title")}</h2>
          <p className="card-sub">{t("reviewer.meta.subtitle")}</p>
        </div>
        <div className="document-meta-panel-status">
          <span className={`badge ${draftComplete ? "ok" : "warn"}`}>
            {draftComplete
              ? <CheckCircle2 size={12} aria-hidden="true" />
              : <AlertTriangle size={12} aria-hidden="true" />}
            {draftComplete ? t("reviewer.meta.statusReady") : t("reviewer.meta.statusIncomplete")}
          </span>
          <button
            type="button"
            className="btn ghost small"
            onClick={() => setOpen(false)}
            disabled={dirty || patch.isPending}
            aria-label={t("common.close")}
            title={dirty ? t("reviewer.meta.unsaved") : t("common.close")}
          >
            <X size={14} />
          </button>
        </div>
      </div>
      {missingFields.length > 0 ? (
        <p className="banner warn">{t("reviewer.meta.required")}</p>
      ) : null}

      <div className="document-meta-fields">
        {fieldEntries.map(([name, definition]) => {
          const label = definition.labels?.[locale] ?? definition.labels?.fr ?? name.replaceAll("_", " ");
          const value = draft[name];
          const formatHint = definition.format_hint?.[locale] ?? definition.format_hint?.fr;
          const invalidFormat = invalidFormatFields.has(name);
          return (
            <label className="field" key={name}>
              <span className="field-label">
                {label}{definition.required ? " *" : ""}
              </span>
              {definition.type === "enum" ? (
                <select
                  className="input"
                  value={String(value ?? "")}
                  onChange={(event) => updateField(name, event.target.value)}
                  required={definition.required}
                >
                  <option value="">{t("reviewer.meta.valueUnset")}</option>
                  {(definition.allowed_values ?? []).map((option) => (
                    <option value={option} key={option}>{option}</option>
                  ))}
                </select>
              ) : definition.type === "string_list" ? (
                <textarea
                  className="input"
                  value={Array.isArray(value) ? value.join("\n") : ""}
                  onChange={(event) =>
                    updateField(
                      name,
                      event.target.value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean),
                    )
                  }
                  maxLength={definition.max_length ?? undefined}
                  aria-label={`${label}. ${t("reviewer.meta.listHint")}`}
                  title={t("reviewer.meta.listHint")}
                  aria-invalid={invalidFormat}
                />
              ) : definition.type === "boolean" ? (
                <input
                  type="checkbox"
                  checked={value === true}
                  onChange={(event) => updateField(name, event.target.checked)}
                />
              ) : (
                <input
                  className="input"
                  type={definition.type === "integer" || definition.type === "number" ? "number" : "text"}
                  step={definition.type === "integer" ? 1 : definition.type === "number" ? "any" : undefined}
                  maxLength={definition.max_length ?? undefined}
                  value={String(value ?? "")}
                  onChange={(event) => updateField(name, event.target.value)}
                  required={definition.required}
                  aria-invalid={invalidFormat}
                />
              )}
              {formatHint ? <span className="hint">{formatHint}</span> : null}
              {invalidFormat ? (
                <span className="error">{t("reviewer.meta.invalidFormat")}</span>
              ) : null}
            </label>
          );
        })}
      </div>

      <div className="document-meta-panel-actions">
        <div className="document-meta-feedback" role="status" aria-live="polite">
          {patch.isPending ? <span className="hint">{t("reviewer.meta.saving")}</span> : null}
          {saveState === "saved" ? <span className="success"><CheckCircle2 size={14} />{t("reviewer.meta.saved")}</span> : null}
          {saveState === "error" ? <span className="error">{t("reviewer.meta.saveError")}</span> : null}
          {dirty && !patch.isPending ? <span className="hint">{t("reviewer.meta.unsaved")}</span> : null}
        </div>
        <div className="row">
          <button
            type="button"
            className="btn secondary small"
            onClick={() => {
              setDraft(savedDraft);
              setSaveState("idle");
            }}
            disabled={!dirty || patch.isPending}
          >
            {t("reviewer.meta.cancel")}
          </button>
          <button
            type="button"
            className="btn primary small"
            onClick={save}
            disabled={!dirty || patch.isPending || invalidFormatFields.size > 0}
          >
            <Save size={14} />
            {patch.isPending ? t("reviewer.meta.saving") : t("reviewer.meta.save")}
          </button>
        </div>
      </div>
    </section>
  );
}