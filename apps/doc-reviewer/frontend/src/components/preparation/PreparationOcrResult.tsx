import { useTranslation } from "react-i18next";

import type { OcrPageResult } from "../../types/preparation";
import { OcrPagePreview } from "./OcrPagePreview";

type Props = {
  imageUrl: string;
  pageLabel: string;
  providerLabel: string;
  data: OcrPageResult | undefined;
  isLoading: boolean;
  error: string | null;
  needsOcr: boolean;
  isCurrentProvider: boolean;
  validated: boolean;
  validating: boolean;
  onValidate: (validated: boolean) => void;
};

export function PreparationOcrResult({
  imageUrl,
  pageLabel,
  providerLabel,
  data,
  isLoading,
  error,
  needsOcr,
  isCurrentProvider,
  validated,
  validating,
  onValidate,
}: Props) {
  const { t } = useTranslation();
  return (
    <div className="preparation-ocr-content" style={{ marginTop: 16 }}>
      <OcrPagePreview
        imageUrl={imageUrl}
        boxes={data?.boxes ?? []}
        pageLabel={pageLabel}
      />
      <section style={{ marginTop: 16 }}>
        <h3 className="card-title">{t("preparation.ocrText")}</h3>
        {isLoading ? (
          <p className="hint">{t("common.loading")}</p>
        ) : data ? (
          <>
            <pre className="preparation-ocr-text">
              {data.text || t("preparation.ocrNoText")}
            </pre>
            {data.boxes.length > 0 ? (
              <p className="label">
                {t("preparation.ocrBoxes", { count: data.boxes.length })}
              </p>
            ) : (
              <p className="hint">{t("preparation.ocrNoBoxes")}</p>
            )}
            <p className="label">
              {providerLabel} · {t("preparation.ocrElapsed", { time: data.elapsed_ms })}
            </p>
          </>
        ) : error ? (
          <p className="error" role="alert">
            {t("preparation.ocrProviderError", { message: error })}
          </p>
        ) : (
          <p className="empty-state">{t("preparation.ocrNoResult")}</p>
        )}
        {isCurrentProvider && needsOcr && data ? (
          <label className="row" style={{ gap: 8, marginTop: 12 }}>
            <input
              type="checkbox"
              checked={validated}
              disabled={validating}
              onChange={(event) => onValidate(event.target.checked)}
            />
            {validated ? t("preparation.ocrValidated") : t("preparation.ocrValidate")}
          </label>
        ) : null}
      </section>
    </div>
  );
}
