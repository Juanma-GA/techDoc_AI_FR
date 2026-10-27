import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { PreparationPageDecision } from "../../types/preparation";

type Props = {
  decision: PreparationPageDecision;
  pageTypeOptions: string[];
  saving: boolean;
  onClassification: (page: number, pageType: string | null, documentPage: string | null) => void;
};

export function PreparationClassificationCell({
  decision,
  pageTypeOptions,
  saving,
  onClassification,
}: Props) {
  const { t } = useTranslation();
  const manualType = decision.page_type_source === "manual" ? decision.page_type : null;
  const manualDocumentPage =
    decision.document_page_source === "manual" ? (decision.document_page ?? "") : "";
  const [pageType, setPageType] = useState(manualType ?? "");
  const [documentPage, setDocumentPage] = useState(manualDocumentPage);
  const source = decision.page_type_source ?? (decision.page_type ? "auto" : "unclassified");
  const status = decision.classification_status ?? source;
  const statusClass = {
    confirmed: "default",
    detected: "default",
    auto: "default",
    manual: "default",
    partial: "warn",
    conflict: "danger",
    unclassified: "warn",
  } as const;
  const evidence = decision.classification_evidence;
  const signals = decision.classification_signals ?? [];
  const notes = decision.classification_notes ?? [];
  const candidates = decision.classification_candidates ?? [];
  const footerLines = evidence?.footer_lines ?? [];
  const footerKey = evidence?.footer_page_key ?? null;
  const unchanged =
    pageType === (manualType ?? "") && documentPage.trim() === manualDocumentPage;
  const options = pageTypeOptions.includes(manualType ?? "")
    ? pageTypeOptions
    : manualType
      ? [...pageTypeOptions, manualType]
      : pageTypeOptions;

  return (
    <div className="prep-type">
      <div className="prep-type-head">
        <strong className="prep-type-name">{decision.page_type ?? "—"}</strong>
        <span className={`badge ${statusClass[status]}`}>
          {t(`preparationUi.classification.source.${status}`)}
        </span>
      </div>
      {candidates.length > 0 ? (
        <p className="prep-type-meta">
          {t("preparationUi.classification.candidates", { value: candidates.join(", ") })}
        </p>
      ) : null}
      {notes.map((note) => (
        <p key={note} className="prep-type-meta">{note}</p>
      ))}
      {decision.document_page ? (
        <p className="prep-type-meta">
          {t("preparationUi.classification.documentPage", { value: decision.document_page })}
        </p>
      ) : null}
      <details className="prep-type-edit">
        <summary>{t("preparationUi.classification.edit")}</summary>
        <div className="prep-type-panel">
          {signals.length > 0 || footerLines.length > 0 || footerKey ? (
            <ul className="prep-type-evidence">
              {signals.map((signal) => (
                <li key={`${signal.section}-${signal.family}-${signal.detail}`}>
                  <span>{signal.section}</span>
                  <span>
                    {t(`preparationUi.classification.family.${signal.family}`)} · {signal.detail}
                  </span>
                </li>
              ))}
              {footerKey ? (
                <li>
                  <span>{t("preparationUi.classification.footerKey", { value: footerKey })}</span>
                </li>
              ) : null}
              {signals.length === 0
                ? footerLines.map((line) => (
                    <li key={line}>
                      <span>{line}</span>
                    </li>
                  ))
                : null}
            </ul>
          ) : (
            <p className="prep-type-meta">{t("preparationUi.classification.noEvidence")}</p>
          )}
          <div className="prep-type-fields">
            <label htmlFor={`page-type-${decision.page}`}>
              <span>{t("preparation.pageType")}</span>
              <select
                id={`page-type-${decision.page}`}
                className="input small"
                value={pageType}
                disabled={saving}
                onChange={(event) => setPageType(event.target.value)}
              >
                <option value="">{t("preparationUi.classification.automatic")}</option>
                {options.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label htmlFor={`document-page-${decision.page}`}>
              <span>{t("preparationUi.classification.documentPageLabel")}</span>
              <input
                id={`document-page-${decision.page}`}
                className="input small"
                value={documentPage}
                maxLength={20}
                disabled={saving}
                onChange={(event) => setDocumentPage(event.target.value)}
              />
            </label>
          </div>
          <button
            type="button"
            className="btn secondary small"
            disabled={saving || unchanged}
            onClick={() =>
              onClassification(decision.page, pageType || null, documentPage.trim() || null)
            }
          >
            {t("preparationUi.classification.save")}
          </button>
        </div>
      </details>
    </div>
  );
}
