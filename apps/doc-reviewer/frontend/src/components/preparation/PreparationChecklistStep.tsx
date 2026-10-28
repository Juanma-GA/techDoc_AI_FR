import { useTranslation } from "react-i18next";

import type { PreparationState } from "../../types/preparation";
import { PreparationDecisionRow } from "./PreparationDecisionRow";
import { PreparationMissingPages } from "./PreparationMissingPages";
import { PreparationSkippedRules } from "./PreparationSkippedRules";

type Props = {
  state: PreparationState;
  error: string | null;
  detecting: boolean;
  savingDecision: boolean;
  onDetect: () => void;
  onDecision: (page: number, isModified: boolean) => void;
  onClassification: (page: number, pageType: string | null) => void;
  onAbsent: (pageTypes: string[], absent: boolean) => void;
  onContinue: () => void;
};

export function PreparationChecklistStep({
  state,
  error,
  detecting,
  savingDecision,
  onDetect,
  onDecision,
  onClassification,
  onAbsent,
  onContinue,
}: Props) {
  const { t } = useTranslation();
  const decisions = state.page_decisions;
  const hasUnknown = decisions.some((decision) => decision.is_modified === null);
  const selectedPages = decisions.filter((decision) => decision.is_modified === true);
  const ocrResults = new Set(
    state.ocr_results_available
      .filter((result) => result.provider === "mistral")
      .map((result) => result.page),
  );
  const unvalidatedPages = state.pages.filter(
    (page) =>
      page.needs_ocr &&
      (!ocrResults.has(page.page) || !state.validated_pages.includes(page.page)),
  );
  const canDetect = state.checklist_rule_count > 0 && unvalidatedPages.length === 0;
  const canContinue =
    decisions.length > 0 &&
    !hasUnknown &&
    selectedPages.length > 0;

  return (
    <section className="card prep-checklist">
      <h2 className="card-title">{t("preparationUi.rulesTitle")}</h2>
      <p className="card-sub">{t("preparationUi.rulesHint")}</p>
      {state.preparation_rule_count > 0 ? (
        <p className="hint prep-checklist-count">
          {t("preparation.builtinRules", { count: state.preparation_rule_count })}
        </p>
      ) : null}
      {state.checklist_source_filename ? (
        <p className="label prep-checklist-count">
          {t("preparationUi.savedImportedRules", {
            filename: state.checklist_source_filename,
            count: state.checklist_imported_rule_count,
          })}
        </p>
      ) : null}
      {state.checklist_rule_count === 0 ? (
        <p className="hint prep-checklist-count">
          {t("preparationUi.noRules")}
        </p>
      ) : null}
      {error ? <p className="error" role="alert">{error}</p> : null}
      {state.checklist_rule_count > 0 ? (
        <div className="prep-checklist-actions">
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
        </div>
      ) : null}

      {decisions.length > 0 ? (
        <div className="prep-checklist-content">
          <PreparationMissingPages
            groups={state.missing_page_types ?? []}
            absentGroups={state.absent_page_types ?? []}
            pageCount={state.page_count}
            saving={savingDecision}
            onProvide={onClassification}
            onAbsent={onAbsent}
          />
          <PreparationSkippedRules rules={state.skipped_rules ?? []} />
          <h3 className="card-title prep-decisions-title">{t("preparation.decisionsTitle")}</h3>
          <div className="table-scroll prep-decisions-scroll">
            <table className="rules-table prep-decisions">
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
                    pageTypeOptions={state.page_type_options ?? []}
                    onDecision={onDecision}
                    onClassification={onClassification}
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
