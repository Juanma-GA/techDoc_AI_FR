import { AlertTriangle, CheckCircle2, Save, Settings2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { usePatchDocumentMeta } from "../../hooks/useDocuments";
import { missingDocumentContext } from "../../types/domain";
import type { Document } from "../../types/domain";
import { ClientMetadataPanel } from "./ClientMetadataPanel";

type Props = {
  document: Document;
};

type DocumentMetaDraft = {
  revisionDate: string;
  cmmNumber: string;
  firstIssueDate: string;
  lastIssueDate: string;
  revisionNumber: string;
  pnrNumber: string;
  manufacturer: "Airbus" | "Boeing";
  documentLanguage: string;
};

function draftFromDocument(document: Document): DocumentMetaDraft {
  return {
    revisionDate: document.meta_revision_date ?? "",
    cmmNumber: document.meta_cmm_number ?? "",
    firstIssueDate: document.meta_first_issue_date ?? "",
    lastIssueDate: document.meta_last_issue_date ?? "",
    revisionNumber: document.meta_revision_number ?? "",
    pnrNumber: document.meta_pnr_number ?? "",
    manufacturer: document.meta_manufacturer ?? "Airbus",
    documentLanguage: document.document_language ?? "",
  };
}

function isDraftComplete(draft: DocumentMetaDraft): boolean {
  return [
    draft.revisionDate,
    draft.cmmNumber,
    draft.firstIssueDate,
    draft.revisionNumber,
    draft.manufacturer,
    draft.documentLanguage,
  ].every((value) => value.trim().length > 0);
}

/**
 * Mapping obligatoire par document. Les valeurs sont jointes au contexte
 * d'analyse du document courant ; elles ne servent pas a compiler la checklist.
 */
function LegacyDocumentMetaPanel({ document }: Props) {
  const { t } = useTranslation();
  const missingContextFields = missingDocumentContext(document);
  const [open, setOpen] = useState(missingContextFields.length > 0);
  const [saveState, setSaveState] = useState<"idle" | "saved" | "error">("idle");
  const patch = usePatchDocumentMeta(document.id);

  const [draft, setDraft] = useState<DocumentMetaDraft>(() => draftFromDocument(document));
  const draftComplete = isDraftComplete(draft);
  const savedDraft = draftFromDocument(document);
  const dirty = JSON.stringify(draft) !== JSON.stringify(savedDraft);

  useEffect(() => {
    setDraft(draftFromDocument(document));
    setSaveState("idle");
  }, [document]);

  useEffect(() => {
    if (missingContextFields.length > 0) setOpen(true);
  }, [missingContextFields.length]);

  function updateField(field: keyof DocumentMetaDraft, value: string): void {
    setSaveState("idle");
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function save(): void {
    setSaveState("idle");
    patch.mutate(
      {
        meta_revision_date: draft.revisionDate.trim() || null,
        meta_cmm_number: draft.cmmNumber.trim() || null,
        meta_first_issue_date: draft.firstIssueDate.trim() || null,
        meta_last_issue_date: draft.lastIssueDate.trim() || null,
        meta_revision_number: draft.revisionNumber.trim() || null,
        meta_pnr_number: draft.pnrNumber.trim() || null,
        meta_manufacturer: draft.manufacturer,
        document_language:
          draft.documentLanguage === "fr" || draft.documentLanguage === "en"
            ? draft.documentLanguage
            : null,
      },
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
            {draftComplete ? <CheckCircle2 size={12} aria-hidden="true" /> : <AlertTriangle size={12} aria-hidden="true" />}
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
      {missingContextFields.length > 0 ? (
        <p className="banner warn">{t("reviewer.meta.required")}</p>
      ) : null}

      <div className="document-meta-fields">
      <label className="field">
        <span className="field-label">{t("reviewer.meta.revisionDate")}</span>
        <input
          className="input"
          value={draft.revisionDate}
          onChange={(e) => updateField("revisionDate", e.target.value)}
          placeholder={t("reviewer.meta.revisionDatePlaceholder")}
        />
      </label>
      <label className="field">
        <span className="field-label">{t("reviewer.meta.cmmNumber")}</span>
        <input
          className="input"
          value={draft.cmmNumber}
          onChange={(e) => updateField("cmmNumber", e.target.value)}
          placeholder={t("reviewer.meta.cmmNumberPlaceholder")}
        />
      </label>
      <label className="field">
        <span className="field-label">{t("reviewer.meta.firstIssueDate")}</span>
        <input
          className="input"
          value={draft.firstIssueDate}
          onChange={(e) => updateField("firstIssueDate", e.target.value)}
          placeholder={t("reviewer.meta.firstIssueDatePlaceholder")}
        />
      </label>
      <label className="field">
        <span className="field-label">{t("reviewer.meta.lastIssueDate")}</span>
        <input
          className="input"
          value={draft.lastIssueDate}
          onChange={(e) => updateField("lastIssueDate", e.target.value)}
          placeholder={t("reviewer.meta.lastIssueDatePlaceholder")}
        />
      </label>
      <label className="field">
        <span className="field-label">{t("reviewer.meta.revisionNumber")}</span>
        <input
          className="input"
          value={draft.revisionNumber}
          onChange={(e) => updateField("revisionNumber", e.target.value)}
          placeholder={t("reviewer.meta.revisionNumberPlaceholder")}
        />
      </label>
      <label className="field">
        <span className="field-label">{t("reviewer.meta.pnrNumber")}</span>
        <input
          className="input"
          value={draft.pnrNumber}
          onChange={(e) => updateField("pnrNumber", e.target.value)}
          placeholder={t("reviewer.meta.pnrNumberPlaceholder")}
        />
      </label>
      <label className="field">
        <span className="field-label">{t("reviewer.meta.manufacturer")}</span>
        <select
          className="input"
          value={draft.manufacturer}
          onChange={(e) => updateField("manufacturer", e.target.value as "Airbus" | "Boeing")}
        >
          <option value="Airbus">{t("reviewer.meta.manufacturerAirbus")}</option>
          <option value="Boeing">{t("reviewer.meta.manufacturerBoeing")}</option>
        </select>
      </label>
      <label className="field">
        <span className="field-label">{t("reviewer.meta.documentLanguage")}</span>
        <select
          className="input"
          value={draft.documentLanguage}
          onChange={(e) => updateField("documentLanguage", e.target.value)}
        >
          <option value="">{t("reviewer.meta.languageUnset")}</option>
          <option value="fr">{t("reviewer.meta.languageFr")}</option>
          <option value="en">{t("reviewer.meta.languageEn")}</option>
        </select>
      </label>
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
          <button type="button" className="btn primary small" onClick={save} disabled={!dirty || patch.isPending}>
            <Save size={14} />
            {patch.isPending ? t("reviewer.meta.saving") : t("reviewer.meta.save")}
          </button>
        </div>
      </div>
    </section>
  );
}

export function DocumentMetaPanel({ document }: Props) {
  return import.meta.env.VITE_LEGACY_RULES_UI === "true" ? (
    <LegacyDocumentMetaPanel document={document} />
  ) : (
    <ClientMetadataPanel document={document} />
  );
}
