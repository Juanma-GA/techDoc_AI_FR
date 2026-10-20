import { useTranslation } from "react-i18next";

import type {
  OcrProvider,
  OcrProviderInfo,
  PreparationPage,
  PreparationState,
} from "../../types/preparation";

type Props = {
  state: PreparationState;
  providers: OcrProviderInfo[];
  provider: OcrProvider;
  pageNumber: number;
  page: PreparationPage | undefined;
  updatingReadability: boolean;
  selectingProvider: boolean;
  runningOcr: boolean;
  onProviderChange: (provider: OcrProvider) => void;
  onSelectProvider: () => void;
  onPageChange: (page: number) => void;
  onSetNeedsOcr: (needsOcr: boolean) => void;
  onRunOcr: () => void;
};

export function PreparationOcrControls({
  state,
  providers,
  provider,
  pageNumber,
  page,
  updatingReadability,
  selectingProvider,
  runningOcr,
  onProviderChange,
  onSelectProvider,
  onPageChange,
  onSetNeedsOcr,
  onRunOcr,
}: Props) {
  const { t } = useTranslation();
  const providerInfo = providers.find((item) => item.id === provider);
  return (
    <>
      <div className="row" style={{ gap: 12, flexWrap: "wrap", margin: "12px 0" }}>
        <label className="label">
          {t("preparation.ocrEngine")}
          <select
            className="input"
            value={provider}
            onChange={(event) => onProviderChange(event.target.value as OcrProvider)}
          >
            {providers.map((item) => (
              <option key={item.id} value={item.id} disabled={!item.available}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        {providerInfo && !providerInfo.available ? (
          <span className="hint">
            {t("preparation.ocrUnavailable", { reason: providerInfo.reason })}
          </span>
        ) : null}
        {providerInfo?.external ? (
          <span className="banner warn" role="note">{t("preparation.ocrExternalNotice")}</span>
        ) : null}
        <button
          type="button"
          className="btn secondary small"
          disabled={
            !providerInfo?.available ||
            selectingProvider ||
            state.selected_provider === provider
          }
          onClick={onSelectProvider}
        >
          {t("preparation.providerSelect")}
        </button>
      </div>

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
          <label className="row" style={{ gap: 8 }}>
            <input
              type="checkbox"
              checked={page.needs_ocr}
              disabled={updatingReadability}
              onChange={(event) => onSetNeedsOcr(event.target.checked)}
            />
            {page.needs_ocr ? t("preparation.ocrNeeds") : t("preparation.ocrReadable")}
          </label>
          <span className="label">
            {t("preparation.ocrNativeChars", { count: page.native_text_chars })}
          </span>
          <button
            type="button"
            className="btn primary small"
            disabled={!page.needs_ocr || !providerInfo?.available || runningOcr}
            onClick={onRunOcr}
          >
            {runningOcr ? t("preparation.ocrRunning") : t("preparation.ocrRun")}
          </button>
        </div>
      ) : null}
    </>
  );
}
