import { useRef } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@internal/ui";
import type { SignaturePlacement } from "./placement";
import { SignatureOverlay } from "./SignatureOverlay";
import { useSignaturePdf } from "./useSignaturePdf";

type PdfSignaturePreviewProps = {
  file: File | null;
  signature: File | null;
  pageNumber: number;
  placement: SignaturePlacement;
  disabled: boolean;
  onPageCount: (count: number) => void;
  onReady: (ready: boolean) => void;
  onPlacementChange: (placement: SignaturePlacement) => void;
};

export function PdfSignaturePreview({
  file,
  signature,
  pageNumber,
  placement,
  disabled,
  onPageCount,
  onReady,
  onPlacementChange,
}: PdfSignaturePreviewProps) {
  const { t } = useTranslation();
  const pageRef = useRef<HTMLDivElement>(null);
  const { canvasRef, hasDocument, pageSize, status } = useSignaturePdf(
    file,
    pageNumber,
    onPageCount,
    onReady,
  );

  return (
    <div className="signature-preview">
      {status === "empty" ? (
        <p className="thumbnail-empty">{t("signature.previewEmpty")}</p>
      ) : null}
      {status === "loading" ? (
        <p className="preview-status" role="status">
          <Spinner aria-label={t("common.loading")} />
          {t("signature.previewLoading")}
        </p>
      ) : null}
      {status === "failed" ? (
        <p className="feedback feedback-error" role="alert">
          {t("signature.previewFailed")}
        </p>
      ) : null}
      {status === "no-pages" ? (
        <p className="feedback feedback-error" role="alert">
          {t("signature.emptyDocument")}
        </p>
      ) : null}
      {hasDocument ? (
        <div
          ref={pageRef}
          className="signature-preview-page"
          style={{ aspectRatio: `${pageSize.width} / ${pageSize.height}` }}
        >
          <canvas ref={canvasRef} aria-label={t("common.page", { page: pageNumber })} />
          {signature && status === "ready" ? (
            <SignatureOverlay
              file={signature}
              pageRef={pageRef}
              pageAspectRatio={pageSize.width / pageSize.height}
              placement={placement}
              disabled={disabled}
              onPlacementChange={onPlacementChange}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
