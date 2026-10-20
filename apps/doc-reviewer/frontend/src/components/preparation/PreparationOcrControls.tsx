import { useTranslation } from "react-i18next";

import type { PreparationPage, PreparationState } from "../../types/preparation";

type Props = {
  state: PreparationState;
  pageNumber: number;
  page: PreparationPage | undefined;
  onPageChange: (page: number) => void;
};

export function PreparationOcrControls({
  state,
  pageNumber,
  page,
  onPageChange,
}: Props) {
  const { t } = useTranslation();
  return (
    <>
      <div className="row" style={{ justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
        <button
          type="button"
          className="btn secondary small"
          disabled={pageNumber <= 1}
          onClick={() => onPageChange(Math.max(1, pageNumber - 1))}
        >
          {t("viewer.prev")}
        </button>
        <label className="label">
          {t("preparation.ocrSelectPage")}
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
        >
          {t("viewer.next")}
        </button>
      </div>

      {page ? (
        <div className="row" style={{ gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <span className="label">
            {t("preparation.ocrNativeChars", { count: page.native_text_chars })}
          </span>
        </div>
      ) : null}
    </>
  );
}
