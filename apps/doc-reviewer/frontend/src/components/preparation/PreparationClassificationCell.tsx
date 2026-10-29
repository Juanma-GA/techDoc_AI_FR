import { useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  PreparationPageDecision,
  PreparationPageTitleOption,
} from "../../types/preparation";

type Props = {
  decision: PreparationPageDecision;
  pageTypeOptions: string[];
  pageTitleOptions: PreparationPageTitleOption[];
  saving: boolean;
  onClassification: (
    page: number,
    pageType: string | null,
    pageTitle: string | null,
  ) => void;
};

export function PreparationClassificationCell({
  decision,
  pageTypeOptions,
  pageTitleOptions,
  saving,
  onClassification,
}: Props) {
  const { t } = useTranslation();
  const manualType = decision.page_type_source === "manual" ? decision.page_type : null;
  const representativeTitle = new Map<string, string>();
  for (const option of pageTitleOptions) {
    if (!representativeTitle.has(option.page_type)) {
      representativeTitle.set(option.page_type, option.title);
    }
  }
  const titleOptionValue = (option: PreparationPageTitleOption) =>
    representativeTitle.get(option.page_type) === option.title
      ? option.page_type
      : `configured-title:${option.title}`;
  const manualTitle = decision.page_type_source === "manual" ? decision.page_title ?? null : null;
  const initialTitle = pageTitleOptions.find((option) => option.title === manualTitle);
  const [pageType, setPageType] = useState(
    initialTitle ? titleOptionValue(initialTitle) : manualType ?? "",
  );
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
  const selectedTitle = pageTitleOptions.find(
    (option) => titleOptionValue(option) === pageType,
  );
  const selectedPageType = selectedTitle?.page_type ?? pageType;
  const unchanged =
    selectedPageType === (manualType ?? "") &&
    (selectedTitle?.title ?? null) === manualTitle;
  const options = pageTypeOptions.includes(manualType ?? "")
    ? pageTypeOptions
    : manualType
      ? [...pageTypeOptions, manualType]
      : pageTypeOptions;
  const titleTypes = new Set(pageTitleOptions.map((option) => option.page_type));
  const otherPageTypes = options.filter((option) => !titleTypes.has(option));

  return (
    <div className="prep-type">
      <div className="prep-type-head">
        <strong className="prep-type-name">
          {decision.page_title ?? decision.page_type ?? "—"}
        </strong>
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
                {pageTitleOptions.length > 0 ? (
                  <optgroup label={t("preparationUi.classification.configuredTitles")}>
                    {pageTitleOptions.map((option) => (
                      <option key={option.title} value={titleOptionValue(option)}>
                        {option.title}
                      </option>
                    ))}
                  </optgroup>
                ) : null}
                {otherPageTypes.length > 0 ? (
                  <optgroup label={t("preparationUi.classification.otherTypes")}>
                    {otherPageTypes.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </optgroup>
                ) : null}
              </select>
            </label>
          </div>
          <button
            type="button"
            className="btn secondary small"
            disabled={saving || unchanged}
            onClick={() => {
              const nextPageType = selectedPageType || null;
              const nextPageTitle = selectedTitle?.title ?? null;
              onClassification(decision.page, nextPageType, nextPageTitle);
              setPageType(
                selectedTitle ? titleOptionValue(selectedTitle) : nextPageType ?? "",
              );
            }}
          >
            {t("preparationUi.classification.save")}
          </button>
        </div>
      </details>
    </div>
  );
}
