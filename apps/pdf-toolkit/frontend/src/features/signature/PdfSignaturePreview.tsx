import { useRef } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@internal/ui";
import type { SignaturePlacement, TextPlacement } from "./placement";
import { SignatureOverlay } from "./SignatureOverlay";
import { TextOverlay } from "./TextOverlay";
import { useSignaturePdf } from "./useSignaturePdf";

type PdfSignaturePreviewProps = {
  file: File | null;
  signature: File | null;
  nameText: string;
  dateText: string;
  pageNumber: number;
  placement: SignaturePlacement;
  namePlacement: TextPlacement;
  datePlacement: TextPlacement;
  disabled: boolean;
  onPageCount: (count: number) => void;
  onReady: (ready: boolean) => void;
  onPlacementChange: (placement: SignaturePlacement) => void;
  onNamePlacementChange: (placement: TextPlacement) => void;
  onDatePlacementChange: (placement: TextPlacement) => void;
};

export function PdfSignaturePreview({
  file,
  signature,
  nameText,
  dateText,
  pageNumber,
  placement,
  namePlacement,
  datePlacement,
  disabled,
  onPageCount,
  onReady,
  onPlacementChange,
  onNamePlacementChange,
  onDatePlacementChange,
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
          {nameText && status === "ready" ? (
            <TextOverlay
              text={nameText}
              label={t("signature.nameOverlayLabel")}
              pageRef={pageRef}
              pageViewportWidth={pageSize.width}
              placement={namePlacement}
              disabled={disabled}
              onPlacementChange={onNamePlacementChange}
            />
          ) : null}
          {dateText && status === "ready" ? (
            <TextOverlay
              text={dateText}
              label={t("signature.dateOverlayLabel")}
              pageRef={pageRef}
              pageViewportWidth={pageSize.width}
              placement={datePlacement}
              disabled={disabled}
              onPlacementChange={onDatePlacementChange}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
