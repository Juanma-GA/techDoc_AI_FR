import { useCallback, useEffect, useRef, useState, type PointerEvent } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { useTranslation } from "react-i18next";

import { Spinner } from "@internal/ui";
import { useSignaturePdf } from "../signature/useSignaturePdf";
import { clampZone, extractValue, type SplitZone } from "./splitModel";
import { readZoneText } from "./zoneText";

type ZonePreviewProps = {
  file: File | null;
  pageNumber: number;
  showZone: boolean;
  zoneEditable: boolean;
  zone: SplitZone;
  valuePattern: RegExp | null;
  disabled: boolean;
  onPageCount: (count: number) => void;
  onDocument: (documentProxy: PDFDocumentProxy | null) => void;
  onZoneChange: (zone: SplitZone) => void;
};

type DragStart = { x: number; y: number; pointerId: number };

export function ZonePreview({
  file,
  pageNumber,
  showZone,
  zoneEditable,
  zone,
  valuePattern,
  disabled,
  onPageCount,
  onDocument,
  onZoneChange,
}: ZonePreviewProps) {
  const { t } = useTranslation();
  const pageRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragStart | null>(null);
  const [zoneText, setZoneText] = useState<string | null>(null);
  const ignoreReady = useCallback(() => undefined, []);
  const { canvasRef, documentProxy, hasDocument, pageSize, status } = useSignaturePdf(
    file,
    pageNumber,
    onPageCount,
    ignoreReady,
  );

  useEffect(() => {
    onDocument(documentProxy && status === "ready" ? documentProxy : null);
  }, [documentProxy, onDocument, status]);

  useEffect(() => {
    setZoneText(null);
    if (!showZone || !documentProxy || status !== "ready") return;
    let active = true;
    const timer = window.setTimeout(() => {
      void documentProxy
        .getPage(pageNumber)
        .then((page) => readZoneText(page, zone))
        .then((text) => {
          if (active) setZoneText(text);
        })
        .catch(() => {
          if (active) setZoneText("");
        });
    }, 200);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [documentProxy, pageNumber, showZone, status, zone]);

  const pointerPosition = (event: PointerEvent<HTMLDivElement>) => {
    const bounds = pageRef.current?.getBoundingClientRect();
    if (!bounds || bounds.width === 0 || bounds.height === 0) return null;
    return {
      x: Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
      y: Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height)),
    };
  };

  const updateDrag = (event: PointerEvent<HTMLDivElement>) => {
    const start = dragRef.current;
    const position = pointerPosition(event);
    if (!start || !position || start.pointerId !== event.pointerId) return;
    onZoneChange(
      clampZone({
        x: Math.min(start.x, position.x),
        y: Math.min(start.y, position.y),
        width: Math.abs(position.x - start.x),
        height: Math.abs(position.y - start.y),
      }),
    );
  };

  const detectedValue = zoneText === null ? null : extractValue(zoneText, valuePattern);

  return (
    <div className="split-preview">
      {status === "empty" ? <p className="thumbnail-empty">{t("split.previewEmpty")}</p> : null}
      {status === "loading" ? (
        <p className="preview-status" role="status">
          <Spinner aria-label={t("common.loading")} />
          {t("split.previewLoading")}
        </p>
      ) : null}
      {status === "failed" || status === "no-pages" ? (
        <p className="feedback feedback-error" role="alert">
          {t("split.previewFailed")}
        </p>
      ) : null}
      {hasDocument ? (
        <div
          ref={pageRef}
          className={`split-preview-page${showZone && zoneEditable && !disabled ? " is-drawable" : ""}`}
          style={{ aspectRatio: `${pageSize.width} / ${pageSize.height}` }}
          onPointerDown={(event) => {
            if (!showZone || !zoneEditable || disabled || event.button !== 0) return;
            const position = pointerPosition(event);
            if (!position) return;
            event.currentTarget.setPointerCapture(event.pointerId);
            dragRef.current = { ...position, pointerId: event.pointerId };
          }}
          onPointerMove={updateDrag}
          onPointerUp={(event) => {
            updateDrag(event);
            dragRef.current = null;
          }}
          onPointerCancel={() => {
            dragRef.current = null;
          }}
        >
          <canvas ref={canvasRef} aria-label={t("common.page", { page: pageNumber })} />
          {showZone && zoneEditable ? (
            <div
              className="split-zone"
              aria-hidden="true"
              style={{
                left: `${zone.x * 100}%`,
                top: `${zone.y * 100}%`,
                width: `${zone.width * 100}%`,
                height: `${zone.height * 100}%`,
              }}
            />
          ) : null}
        </div>
      ) : null}
      {showZone && hasDocument ? (
        <div className="split-zone-reading" role="status">
          <span>{t("split.zoneText")}</span>
          <code>{zoneText === null ? "..." : zoneText || t("split.zoneTextEmpty")}</code>
          <span>{t("split.zoneValue")}</span>
          <code className={detectedValue ? "is-found" : "is-missing"}>
            {detectedValue === null ? "..." : detectedValue || t("split.zoneValueEmpty")}
          </code>
        </div>
      ) : null}
    </div>
  );
}
