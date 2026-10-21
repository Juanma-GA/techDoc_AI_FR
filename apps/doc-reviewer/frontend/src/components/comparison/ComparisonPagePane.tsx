import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { bboxToPercentRect } from "../../lib/bbox";
import {
  comparisonApi,
  type ComparisonPageAlignment,
  type ComparisonPageSlot,
  type ComparisonChange,
} from "../../lib/comparisonApi";

type Props = {
  comparisonId: string;
  documentIndex: number;
  filename: string;
  pageNumber: number | null;
  side: "reference" | "comparison";
  changes: ComparisonChange[];
  selectedGroupId: string | null;
  unavailableMessage: string;
  onSelectGroup: (groupId: string) => void;
};

export function ComparisonPagePane({
  comparisonId,
  documentIndex,
  filename,
  pageNumber,
  side,
  changes,
  selectedGroupId,
  unavailableMessage,
  onSelectGroup,
}: Props) {
  const { t } = useTranslation();
  const [imageError, setImageError] = useState(false);

  useEffect(() => setImageError(false), [comparisonId, documentIndex, pageNumber]);

  const visibleChanges = pageNumber === null
    ? []
    : changes.filter((change) =>
        change.page === pageNumber &&
        change.kind === (side === "reference" ? "removed" : "added"),
      );

  return (
    <section
      className="comparison-pane"
      aria-label={`${filename} ${t(side === "reference" ? "comparison.referencePane" : "comparison.candidatePane")}`}
    >
      <header className="comparison-pane-header">
        <h3>{filename}</h3>
        {pageNumber !== null ? (
          <span className="label">{t("comparison.page", { page: pageNumber })}</span>
        ) : null}
      </header>
      {pageNumber === null ? (
        <div className="comparison-page-placeholder" role="status">
          {unavailableMessage}
        </div>
      ) : imageError ? (
        <div className="comparison-page-placeholder" role="alert">
          {t("comparison.pageRenderError")}
        </div>
      ) : (
        <div className="comparison-page-viewport">
          <div className="comparison-page-surface">
            <img
              className="comparison-page-image"
              src={comparisonApi.pageImageUrl(comparisonId, documentIndex, pageNumber)}
              alt={t("comparison.pageAlt", { filename, page: pageNumber })}
              onError={() => setImageError(true)}
              draggable={false}
            />
            <div className="comparison-page-overlay">
              {visibleChanges.map((change, index) => {
                const rect = change.bbox ? bboxToPercentRect(change.bbox) : null;
                if (!rect) return null;
                const selected = selectedGroupId === change.group_id;
                return (
                  <button
                    key={`${change.group_id}-${change.kind}-${index}`}
                    type="button"
                    className={`comparison-diff-box comparison-diff-box--${change.kind}${selected ? " is-selected" : ""}`}
                    style={{
                      left: `${rect.left}%`,
                      top: `${rect.top}%`,
                      width: `${rect.width}%`,
                      height: `${rect.height}%`,
                    }}
                    aria-pressed={selected}
                    aria-label={t("comparison.boxDescription", {
                      kind: t(`comparison.${change.kind}`),
                      page: change.page,
                      text: change.text,
                    })}
                    title={`${t(`comparison.${change.kind}`)}: ${change.text}`}
                    onClick={() => onSelectGroup(change.group_id)}
                  />
                );
              })}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export function ComparisonAlignmentStatus({
  slot,
  alignment,
}: {
  slot: ComparisonPageSlot | undefined;
  alignment: ComparisonPageAlignment | undefined;
}) {
  const { t } = useTranslation();
  if (!slot) {
    return <p className="comparison-alignment-status" role="status">{t("comparison.noAlignment")}</p>;
  }
  if (!alignment) {
    return <p className="comparison-alignment-status" role="status">{t("comparison.pageSlotFromOtherVersion")}</p>;
  }

  const messages: string[] = [];
  if (alignment.status === "changed") messages.push(t("comparison.pageTextChanged"));
  if (alignment.status === "reference_only") messages.push(t("comparison.pageMissingInVersion"));
  if (alignment.status === "comparison_only") messages.push(t("comparison.pageExtraInVersion"));
  if (
    alignment.reference_page !== null &&
    alignment.comparison_page !== null &&
    alignment.reference_page !== alignment.comparison_page
  ) {
    messages.push(
      t("comparison.pageNumbersDiffer", {
        reference: alignment.reference_page,
        comparison: alignment.comparison_page,
      }),
    );
  }
  return messages.length ? (
    <p className="comparison-alignment-status" role="status">{messages.join(" · ")}</p>
  ) : null;
}
