import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useOcrPageResult } from "../../hooks/usePreparation";
import { API_BASE_URL } from "../../lib/api";
import type {
  OcrProvider,
  OcrProviderInfo,
  PreparationState,
} from "../../types/preparation";
import { PreparationOcrControls } from "./PreparationOcrControls";
import { PreparationOcrResult } from "./PreparationOcrResult";
import "../../styles/preparation.css";

type Props = {
  documentId: string;
  state: PreparationState;
  providers: OcrProviderInfo[];
  error: string | null;
  onSetProvider: (provider: OcrProvider) => void;
  selectingProvider: boolean;
  onSetNeedsOcr: (page: number, needsOcr: boolean) => void;
  updatingReadability: boolean;
  onRunOcr: (page: number, provider: OcrProvider) => void;
  runningOcr: boolean;
  onValidate: (page: number, provider: OcrProvider, validated: boolean) => void;
  validating: boolean;
};

export function PreparationOcrStep({
  documentId,
  state,
  providers,
  error,
  onSetProvider,
  selectingProvider,
  onSetNeedsOcr,
  updatingReadability,
  onRunOcr,
  runningOcr,
  onValidate,
  validating,
}: Props) {
  const { t } = useTranslation();
  const [testProvider, setTestProvider] = useState<OcrProvider>("mistral");
  const [pageNumber, setPageNumber] = useState(1);
  const page = state.pages.find((item) => item.page === pageNumber);
  const hasResult = (provider: OcrProvider) =>
    state.ocr_results_available.some(
      (item) => item.provider === provider && item.page === pageNumber,
    );
  const results = {
    mistral: useOcrPageResult(documentId, pageNumber, "mistral", hasResult("mistral")),
    paddle: useOcrPageResult(documentId, pageNumber, "paddle", hasResult("paddle")),
    indra: useOcrPageResult(documentId, pageNumber, "indra", hasResult("indra")),
  };
  const displayedProviders = providers.filter(
    (provider) => provider.id === testProvider || hasResult(provider.id),
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
      <PreparationOcrControls
        state={state}
        providers={providers}
        provider={testProvider}
        pageNumber={pageNumber}
        page={page}
        updatingReadability={updatingReadability}
        selectingProvider={selectingProvider}
        runningOcr={runningOcr}
        onProviderChange={setTestProvider}
        onSelectProvider={() => onSetProvider(testProvider)}
        onPageChange={setPageNumber}
        onSetNeedsOcr={(needsOcr) => onSetNeedsOcr(pageNumber, needsOcr)}
        onRunOcr={() => onRunOcr(pageNumber, testProvider)}
      />
      {state.selected_provider ? (
        <p className="hint" style={{ marginTop: 8 }}>
          {t("preparation.ocrSelected")}:{" "}
          {providers.find((provider) => provider.id === state.selected_provider)?.label}
        </p>
      ) : null}
      <div className="preparation-ocr-comparison">
        {displayedProviders.map((provider) => {
          const result = results[provider.id];
          const isSelected = state.selected_provider === provider.id;
          return (
            <section
              className="preparation-ocr-engine"
              key={provider.id}
              aria-label={provider.label}
            >
              <h3 className="card-title">{provider.label}</h3>
              <PreparationOcrResult
                imageUrl={`${API_BASE_URL}/documents/${documentId}/pages/${pageNumber}.png`}
                pageLabel={pageLabel}
                providerLabel={provider.label}
                data={result.data}
                isLoading={result.isLoading}
                error={result.isError ? result.error.message : null}
                needsOcr={Boolean(page?.needs_ocr)}
                isCurrentProvider={isSelected}
                validated={isSelected && state.validated_pages.includes(pageNumber)}
                validating={validating}
                onValidate={(value) => onValidate(pageNumber, provider.id, value)}
              />
            </section>
          );
        })}
      </div>
    </section>
  );
}
