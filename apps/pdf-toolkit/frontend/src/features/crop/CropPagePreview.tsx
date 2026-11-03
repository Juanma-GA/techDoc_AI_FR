import { useRef, useState, type PointerEvent, type RefObject } from "react";
import { useTranslation } from "react-i18next";

import type { CropRegion } from "./cropGeometry";

type CropPagePreviewProps = {
  canvasRef: RefObject<HTMLCanvasElement>;
  pageSize: { width: number; height: number };
  ready: boolean;
  disabled: boolean;
  region: CropRegion | null;
  onRegionChange: (region: CropRegion | null) => void;
};

type DragStart = { x: number; y: number; pointerId: number };

export function CropPagePreview({
  canvasRef,
  pageSize,
  ready,
  disabled,
  region,
  onRegionChange,
}: CropPagePreviewProps) {
  const { t } = useTranslation();
  const pageRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragStart | null>(null);
  const [draftRegion, setDraftRegion] = useState<CropRegion | null>(null);

  const pointerPosition = (event: PointerEvent<HTMLDivElement>) => {
    const bounds = pageRef.current?.getBoundingClientRect();
    if (!bounds || bounds.width === 0 || bounds.height === 0) return null;
    return {
      x: Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
      y: Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height)),
    };
  };

  const regionAt = (event: PointerEvent<HTMLDivElement>) => {
    const start = dragRef.current;
    const position = pointerPosition(event);
    if (!start || !position || start.pointerId !== event.pointerId) return null;
    return {
      left: Math.min(start.x, position.x),
      top: Math.min(start.y, position.y),
      right: Math.max(start.x, position.x),
      bottom: Math.max(start.y, position.y),
    };
  };
  const activeRegion = draftRegion ?? region;

  return (
    <div
      ref={pageRef}
      className={`crop-preview-page${ready ? " is-ready" : ""}${ready && !disabled ? " is-drawable" : ""}`}
      style={{ aspectRatio: `${pageSize.width} / ${pageSize.height}` }}
      onPointerDown={(event) => {
        if (!ready || disabled || event.button !== 0) return;
        const position = pointerPosition(event);
        if (!position) return;
        event.currentTarget.setPointerCapture?.(event.pointerId);
        dragRef.current = { ...position, pointerId: event.pointerId };
        const initialRegion = {
          left: position.x,
          top: position.y,
          right: position.x,
          bottom: position.y,
        };
        setDraftRegion(initialRegion);
      }}
      onPointerMove={(event) => {
        const nextRegion = regionAt(event);
        if (nextRegion) setDraftRegion(nextRegion);
      }}
      onPointerUp={(event) => {
        const nextRegion = regionAt(event);
        if (nextRegion && nextRegion.right - nextRegion.left >= 0.01 && nextRegion.bottom - nextRegion.top >= 0.01) {
          onRegionChange(nextRegion);
        } else if (nextRegion) {
          onRegionChange(null);
        }
        dragRef.current = null;
        setDraftRegion(null);
      }}
      onPointerCancel={() => {
        dragRef.current = null;
        setDraftRegion(null);
      }}
    >
      <canvas ref={canvasRef} aria-label={t("crop.previewPage", { page: 1 })} />
      {activeRegion ? (
        <div
          className="crop-selection"
          style={{
            left: `${activeRegion.left * 100}%`,
            top: `${activeRegion.top * 100}%`,
            width: `${(activeRegion.right - activeRegion.left) * 100}%`,
            height: `${(activeRegion.bottom - activeRegion.top) * 100}%`,
          }}
          aria-hidden="true"
        />
      ) : null}
    </div>
  );
}
