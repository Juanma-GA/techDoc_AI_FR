import { useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  PreparationState,
} from "../../types/preparation";
import { API_BASE_URL } from "../../lib/api";
import { PreparationDecisionRow } from "./PreparationDecisionRow";

type Props = {
  state: PreparationState;
  error: string | null;
  importMessage: string | null;
  importing: boolean;
  detecting: boolean;
  savingDecision: boolean;
  onImport: (file: File) => void;
  onDetect: () => void;
  onDecision: (page: number, isModified: boolean) => void;
  onContinue: () => void;
};

export function PreparationChecklistStep({
  state,
  error,
  importMessage,
  importing,
  detecting,
  savingDecision,
  onImport,
  onDetect,
  onDecision,
  onContinue,
}: Props) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const decisions = state.page_decisions;
  const hasUnknown = decisions.some((decision) => decision.is_modified === null);
  const selectedPages = decisions.filter((decision) => decision.is_modified === true);
  const unreadablePages = state.pages.filter((page) => page.needs_ocr);
  const unvalidatedPages = unreadablePages.filter(
    (page) => !state.validated_pages.includes(page.page),
  );
  const canDetect =
    state.checklist_rule_count > 0 &&
    (unreadablePages.length === 0 ||
      (Boolean(state.selected_provider) && unvalidatedPages.length === 0));
  const canContinue =
    decisions.length > 0 &&
    !hasUnknown &&
    selectedPages.length > 0;

  return (
    <section className="card">
      <h2 className="card-title">{t("preparation.checklistTitle")}</h2>
      <p className="card-sub">{t("preparation.checklistHint")}</p>
      <div className="row" style={{ gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <a className="btn ghost small" href={`${API_BASE_URL}/preparation/checklist/template`}>
          {t("preparation.checklistTemplate")}
        </a>
        <input
          type="file"
          accept=".xlsx,.xlsm"
          aria-label={t("preparation.checklistUpload")}
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          disabled={importing}
        />
        <button
          type="button"
          className="btn secondary small"
          disabled={!file || importing}
          onClick={() => file && onImport(file)}
        >
          {importing ? t("preparation.checklistImporting") : t("preparation.checklistUpload")}
        </button>
      </div>
      {state.checklist_source_filename ? (
        <p className="label" style={{ marginTop: 8 }}>
          {t("preparation.checklistSource", {
            filename: state.checklist_source_filename,
            count: state.checklist_rule_count,
          })}
        </p>
      ) : (
        <p className="hint" style={{ marginTop: 8 }}>{t("preparation.checklistMissing")}</p>
      )}
      {importMessage ? <p className="banner info">{importMessage}</p> : null}
      {error ? <p className="error" role="alert">{error}</p> : null}
      {state.checklist_rule_count > 0 ? (
        <>
          <button
            type="button"
            className="btn primary small"
            disabled={!canDetect || detecting}
            onClick={onDetect}
          >
            {detecting ? t("preparation.detectingPages") : t("preparation.detectPages")}
          </button>
          {unvalidatedPages.length > 0 ? (
            <p className="hint">{t("preparation.providerNotReady")}</p>
          ) : null}
        </>
      ) : null}

      {decisions.length > 0 ? (
        <div style={{ marginTop: 16 }}>
          <h3 className="card-title">{t("preparation.decisionsTitle")}</h3>
          <div className="table-scroll">
            <table className="rules-table">
              <thead>
                <tr>
                  <th>{t("preparation.page")}</th>
                  <th>{t("preparation.pageType")}</th>
                  <th>{t("preparation.decision")}</th>
                  <th>{t("preparation.reasons")}</th>
                  <th>{t("preparation.manualOverride")}</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((decision) => (
                  <PreparationDecisionRow
                    key={decision.page}
                    decision={decision}
                    saving={savingDecision}
                    onDecision={onDecision}
                  />
                ))}
              </tbody>
            </table>
          </div>
          {hasUnknown ? <p className="hint">{t("preparation.resolvePages")}</p> : null}
          {selectedPages.length === 0 ? (
            <p className="hint">{t("preparation.noPagesSelected")}</p>
          ) : null}
          <button
            type="button"
            className="btn primary"
            disabled={!canContinue}
            onClick={onContinue}
          >
            {t("preparation.continueReview")}
          </button>
        </div>
      ) : null}
    </section>
  );
}
