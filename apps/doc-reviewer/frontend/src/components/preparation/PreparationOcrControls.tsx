import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { PreparationState } from "../../types/preparation";

type Props = {
  state: PreparationState;
  pageNumber: number;
  onPageChange: (page: number) => void;
};

export function PreparationOcrControls({
  state,
  pageNumber,
  onPageChange,
}: Props) {
  const { t } = useTranslation();
  return (
    <div className="preparation-page-controls">
      <div className="preparation-page-nav">
        <button
          type="button"
          className="btn secondary small"
          disabled={pageNumber <= 1}
          onClick={() => onPageChange(Math.max(1, pageNumber - 1))}
          aria-label={t("viewer.prev")}
        >
          <ChevronLeft size={16} aria-hidden="true" />
        </button>
        <label className="preparation-page-select">
          <span className="sr-only">{t("preparation.ocrSelectPage")}</span>
          <select
            className="input"
            value={pageNumber}
            onChange={(event) => onPageChange(Number(event.target.value))}
          >
            {state.pages.map((item) => (
              <option key={item.page} value={item.page}>
                {t("preparation.ocrPage", {
                  page: item.page,
                  count: state.page_count,
                })}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="btn secondary small"
          disabled={pageNumber >= state.page_count}
          onClick={() =>
            onPageChange(Math.min(state.page_count, pageNumber + 1))
          }
          aria-label={t("viewer.next")}
        >
          <ChevronRight size={16} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
