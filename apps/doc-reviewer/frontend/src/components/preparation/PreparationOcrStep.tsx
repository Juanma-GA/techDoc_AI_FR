import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useOcrPageResult } from "../../hooks/usePreparation";
import { API_BASE_URL } from "../../lib/api";
import type { PreparationState } from "../../types/preparation";
import { PreparationOcrControls } from "./PreparationOcrControls";
import { PreparationOcrResult } from "./PreparationOcrResult";
import "../../styles/preparation.css";

type Props = {
  documentId: string;
  state: PreparationState;
  error: string | null;
  onRunOcrAll: () => void;
  runningOcrAll: boolean;
  onValidateAllAndAnalyze: () => void;
  validatingAll: boolean;
  analyzing: boolean;
};

export function PreparationOcrStep({
  documentId,
  state,
  error,
  onRunOcrAll,
  runningOcrAll,
  onValidateAllAndAnalyze,
  validatingAll,
  analyzing,
}: Props) {
  const { t } = useTranslation();
  const [pageNumber, setPageNumber] = useState(1);
  const page = state.pages.find((item) => item.page === pageNumber);
  const hasResult = state.ocr_results_available.some(
    (item) => item.provider === "mistral" && item.page === pageNumber,
  );
  const result = useOcrPageResult(documentId, pageNumber, "mistral", hasResult);
  const ocrComplete =
    state.pages.length === state.page_count &&
    state.page_count > 0 &&
    state.pages.every((item) =>
      state.ocr_results_available.some(
        (entry) => entry.provider === "mistral" && entry.page === item.page,
      ),
    );
  const pageLabel = t("preparation.ocrPage", {
    page: pageNumber,
    count: state.page_count,
  });

  return (
    <section className="card">
      <div className="row" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h2 className="card-title">{t("preparation.ocrTitle")}</h2>
          <p className="card-sub">{t("preparation.ocrHint")}</p>
        </div>
        <span className="badge info">
          {t("preparation.sourceDocument", {
            filename: state.source_filename,
            count: state.page_count,
          })}
        </span>
      </div>
      {error ? <p className="error" role="alert">{error}</p> : null}
      <div className="row" style={{ gap: 10, flexWrap: "wrap", margin: "12px 0" }}>
        <span className="badge info">Mistral OCR</span>
        <button
          type="button"
          className="btn primary small"
          disabled={runningOcrAll}
          onClick={onRunOcrAll}
        >
          {runningOcrAll
            ? t("preparation.ocrRunning")
            : ocrComplete
              ? t("preparation.rerunOcrAll")
              : t("preparation.runOcrAll")}
        </button>
      </div>
      <PreparationOcrControls
        state={state}
        pageNumber={pageNumber}
        page={page}
        onPageChange={setPageNumber}
      />
      <div className="preparation-ocr-comparison">
        <section className="preparation-ocr-engine" aria-label="Mistral OCR">
          <PreparationOcrResult
            imageUrl={`${API_BASE_URL}/documents/${documentId}/pages/${pageNumber}.png`}
            pageLabel={pageLabel}
            providerLabel="Mistral OCR"
            data={result.data}
            isLoading={result.isLoading}
            error={result.isError ? result.error.message : null}
          />
        </section>
      </div>
      {ocrComplete ? (
        <button
          type="button"
          className="btn primary"
          style={{ marginTop: 16 }}
          disabled={runningOcrAll || validatingAll || analyzing}
          onClick={onValidateAllAndAnalyze}
        >
          {validatingAll
            ? t("preparation.validatingAll")
            : analyzing
              ? t("preparation.detectingPages")
              : t("preparation.validateAllAndAnalyze")}
        </button>
      ) : null}
    </section>
  );
}
