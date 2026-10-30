import { AlertTriangle, CheckCircle2, Save, Settings2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useClientConfig } from "../../hooks/useClientConfig";
import { usePatchDocumentMeta } from "../../hooks/useDocuments";
import type { Document } from "../../types/domain";
import { ClientMetadataFields } from "./ClientMetadataFields";
import {
  createClientMetadataDraft,
  hasClientMetadataValue,
  matchesClientMetadataPattern,
  serializeClientMetadataValue,
} from "./clientMetadataForm";
import type { ClientMetadataDraft } from "./clientMetadataForm";
import { MetadataSuggestionsControl } from "./MetadataSuggestionsControl";
import { resetMappingWithSuggestions } from "./metadataSuggestions";

type Props = {
  document: Document;
  mappingValues?: Record<string, unknown>;
  onSaveMapping?: (values: Record<string, unknown>) => Promise<void>;
  titleKey?: string;
  subtitleKey?: string;
};

export function ClientMetadataPanel({
  document,
  mappingValues,
  onSaveMapping,
  titleKey = "reviewer.meta.title",
  subtitleKey = "reviewer.meta.subtitle",
}: Props) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language.toLowerCase().startsWith("en") ? "en" : "fr";
  const config = useClientConfig();
  const fields = config.data?.mapping.fields ?? {};
  const fieldEntries = Object.entries(fields);
  const requiredFields = fieldEntries
    .filter(([, definition]) => definition.required)
    .map(([name]) => name);
  const [draft, setDraft] = useState<ClientMetadataDraft>(
    () => createClientMetadataDraft(document, fields, mappingValues),
  );
  const missingFields = requiredFields.filter(
    (name) => !hasClientMetadataValue(draft[name]),
  );
  const [open, setOpen] = useState(missingFields.length > 0);
  const [saveState, setSaveState] = useState<"idle" | "saved" | "error">("idle");
  const [savingMapping, setSavingMapping] = useState(false);
  const patch = usePatchDocumentMeta(document.id);

  useEffect(() => {
    setDraft(
      createClientMetadataDraft(
        document,
        config.data?.mapping.fields ?? {},
        mappingValues,
      ),
    );
    setSaveState("idle");
  }, [document, config.data, mappingValues]);

  useEffect(() => {
    if (missingFields.length > 0) setOpen(true);
  }, [missingFields.length]);

  if (config.isLoading) {
    return <p className="hint">{t("common.loading")}</p>;
  }
  if (config.isError || !config.data) {
    return <p className="banner warn">{t("rules.client.loadFailed")}</p>;
  }

  const savedDraft = createClientMetadataDraft(document, fields, mappingValues);
  const dirty = JSON.stringify(draft) !== JSON.stringify(savedDraft);
  const draftComplete = requiredFields.every((field) => hasClientMetadataValue(draft[field]));
  const invalidFormatFields = new Set(
    fieldEntries
      .filter(([name, definition]) => !matchesClientMetadataPattern(draft[name], definition))
      .map(([name]) => name),
  );
  const isPending = patch.isPending || savingMapping;

  function updateField(name: string, value: unknown): void {
    setSaveState("idle");
    setDraft((current) => ({ ...current, [name]: value }));
  }

  function save(): void {
    if (invalidFormatFields.size > 0) return;
    const clientMetadata = Object.fromEntries(
      fieldEntries.map(([name, definition]) => [
        name,
        serializeClientMetadataValue(draft[name], definition),
      ]),
    );
    setSaveState("idle");
    if (onSaveMapping) {
      setSavingMapping(true);
      void onSaveMapping(clientMetadata)
        .then(() => {
          setSaveState("saved");
          if (draftComplete) setOpen(false);
        })
        .catch(() => setSaveState("error"))
        .finally(() => setSavingMapping(false));
      return;
    }
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
            <div className="document-meta-panel-title">{t(titleKey)}</div>
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
          <h2 id="document-meta-title" className="card-title">{t(titleKey)}</h2>
          <p className="card-sub">{t(subtitleKey)}</p>
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
            disabled={dirty || isPending}
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

      {document.working_format === "pdf" ? (
        <MetadataSuggestionsControl
          documentId={document.id}
          onApply={(suggestions) => {
            setDraft(resetMappingWithSuggestions(fields, suggestions));
            setSaveState("idle");
          }}
        />
      ) : null}

      <ClientMetadataFields
        entries={fieldEntries}
        draft={draft}
        locale={locale}
        invalidFields={invalidFormatFields}
        onChange={updateField}
      />

      <div className="document-meta-panel-actions">
        <div className="document-meta-feedback" role="status" aria-live="polite">
          {isPending ? <span className="hint">{t("reviewer.meta.saving")}</span> : null}
          {saveState === "saved" ? <span className="success"><CheckCircle2 size={14} />{t("reviewer.meta.saved")}</span> : null}
          {saveState === "error" ? <span className="error">{t("reviewer.meta.saveError")}</span> : null}
          {dirty && !isPending ? <span className="hint">{t("reviewer.meta.unsaved")}</span> : null}
        </div>
        <div className="row">
          <button
            type="button"
            className="btn secondary small"
            onClick={() => {
              setDraft(savedDraft);
              setSaveState("idle");
            }}
            disabled={!dirty || isPending}
          >
            {t("reviewer.meta.cancel")}
          </button>
          <button
            type="button"
            className="btn primary small"
            onClick={save}
            disabled={!dirty || isPending || invalidFormatFields.size > 0}
          >
            <Save size={14} />
            {isPending ? t("reviewer.meta.saving") : t("reviewer.meta.save")}
          </button>
        </div>
      </div>
    </section>
  );
}