import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  useOcrPageResult,
  usePreparationNativeText,
} from "../../hooks/usePreparation";
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
  onRunOcrPage: (page: number) => void;
  runningOcrPage: boolean;
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
  onRunOcrPage,
  runningOcrPage,
}: Props) {
  const { t } = useTranslation();
  const [pageNumber, setPageNumber] = useState(1);
  const page = state.pages.find((item) => item.page === pageNumber);
  const hasResult = state.ocr_results_available.some(
    (item) => item.provider === "mistral" && item.page === pageNumber,
  );
  const result = useOcrPageResult(documentId, pageNumber, "mistral", hasResult);
  const nativeText = usePreparationNativeText(
    documentId,
    pageNumber,
    Boolean(page && !page.needs_ocr),
  );
  const ocrComplete =
    state.pages.length === state.page_count &&
    state.page_count > 0 &&
    state.pages.every(
      (item) =>
        !item.needs_ocr ||
        state.ocr_results_available.some(
          (entry) => entry.provider === "mistral" && entry.page === item.page,
        ),
    );
  const pendingOcrCount = state.pages.filter(
    (item) =>
      item.needs_ocr &&
      !state.ocr_results_available.some(
        (entry) => entry.provider === "mistral" && entry.page === item.page,
      ),
  ).length;
  const pageLabel = t("preparation.ocrPage", {
    page: pageNumber,
    count: state.page_count,
  });

  return (
    <section className="card">
      <div className="preparation-ocr-header">
        <div>
          <h2 className="card-title">{t("preparation.ocrTitle")}</h2>
          <p className="card-sub">{t("preparationUi.ocrHint")}</p>
        </div>
        <div className="preparation-ocr-actions">
          {pendingOcrCount > 0 ? (
            <button
              type="button"
              className="btn secondary small"
              disabled={runningOcrAll || runningOcrPage || validatingAll || analyzing}
              onClick={onRunOcrAll}
            >
              {runningOcrAll
                ? t("preparationUi.ocrPendingRunning")
                : t("preparationUi.ocrPending", { count: pendingOcrCount })}
            </button>
          ) : null}
          <button
            type="button"
            className="btn primary small"
            disabled={
              !ocrComplete ||
              runningOcrAll ||
              runningOcrPage ||
              validatingAll ||
              analyzing
            }
            onClick={onValidateAllAndAnalyze}
          >
            {validatingAll
              ? t("preparation.validatingAll")
              : analyzing
                ? t("preparation.detectingPages")
                : state.pages.some((item) => item.needs_ocr)
                  ? t("preparation.validateAllAndAnalyze")
                  : t("preparationUi.analyzePages")}
          </button>
        </div>
      </div>
      <p className="preparation-source-document badge info">
        {t("preparation.sourceDocument", {
          filename: state.source_filename,
          count: state.page_count,
        })}
      </p>
      {error ? <p className="error" role="alert">{error}</p> : null}
      <PreparationOcrControls
        state={state}
        pageNumber={pageNumber}
        onPageChange={setPageNumber}
      />
      {page ? (
        <div className="preparation-ocr-page-state">
          <span className={`badge ${page.needs_ocr ? "warn" : "ok"}`}>
            {page.needs_ocr
              ? t("preparationUi.ocrRequired")
              : t("preparationUi.nativeTextUsed")}
          </span>
          <span className="label">
            {t("preparation.ocrNativeChars", { count: page.native_text_chars })}
          </span>
          {page.needs_ocr && (
            <button
              type="button"
              className="btn secondary small"
              disabled={runningOcrAll || runningOcrPage || validatingAll || analyzing}
              onClick={() => onRunOcrPage(pageNumber)}
            >
              {runningOcrPage
                ? t("preparation.ocrRunning")
                : hasResult
                  ? t("preparationUi.rerunCurrentOcr")
                  : t("preparationUi.runCurrentOcr")}
            </button>
          )}
        </div>
      ) : null}
      <div className="preparation-ocr-comparison">
        <section className="preparation-ocr-engine" aria-label="Mistral OCR">
          <PreparationOcrResult
            imageUrl={`${API_BASE_URL}/documents/${documentId}/pages/${pageNumber}.png`}
            pageLabel={pageLabel}
            providerLabel="Mistral OCR"
            data={result.data}
            isLoading={result.isLoading}
            error={result.isError ? result.error.message : null}
            nativeText={nativeText.data?.text}
            nativeTextLoading={nativeText.isLoading}
            nativeTextError={nativeText.isError ? nativeText.error.message : null}
          />
        </section>
      </div>
    </section>
  );
}
