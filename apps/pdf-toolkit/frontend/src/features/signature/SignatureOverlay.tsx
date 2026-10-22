import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  clampSignaturePlacement,
  resizeSignaturePlacement,
  signatureHeight,
  type SignaturePlacement,
} from "./placement";
import { SignatureResizeHandles } from "./SignatureResizeHandles";

type SignatureOverlayProps = {
  file: File;
  pageRef: React.RefObject<HTMLDivElement | null>;
  pageAspectRatio: number;
  placement: SignaturePlacement;
  disabled: boolean;
  onPlacementChange: (placement: SignaturePlacement) => void;
};

type DragState = {
  pointerId: number;
  startX: number;
  startY: number;
  placement: SignaturePlacement;
};

export function SignatureOverlay({
  file,
  pageRef,
  pageAspectRatio,
  placement,
  disabled,
  onPlacementChange,
}: SignatureOverlayProps) {
  const { t } = useTranslation();
  const overlayRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<DragState | null>(null);
  const [imageUrl, setImageUrl] = useState("");
  const [imageAspectRatio, setImageAspectRatio] = useState(3.2);

  useEffect(() => {
    const objectUrl = URL.createObjectURL(file);
    setImageUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  useEffect(() => {
    if (!imageUrl || pageAspectRatio <= 0) return;
    const clamped = clampSignaturePlacement(placement, pageAspectRatio, imageAspectRatio);
    if (
      clamped.x !== placement.x ||
      clamped.y !== placement.y ||
      clamped.width !== placement.width
    ) {
      onPlacementChange(clamped);
    }
  }, [imageAspectRatio, imageUrl, onPlacementChange, pageAspectRatio, placement]);

  const beginDrag = (event: PointerEvent<HTMLButtonElement>) => {
    if (disabled || !pageRef.current || event.button !== 0) return;
    event.preventDefault();
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      placement,
    };
    if (typeof event.currentTarget.setPointerCapture === "function") {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  };

  const moveSignature = (event: PointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    const pageBounds = pageRef.current?.getBoundingClientRect();
    if (!drag || drag.pointerId !== event.pointerId || !pageBounds || pageBounds.width === 0) return;
    onPlacementChange(
      clampSignaturePlacement(
        {
          ...drag.placement,
          x: drag.placement.x + (event.clientX - drag.startX) / pageBounds.width,
          y: drag.placement.y + (event.clientY - drag.startY) / pageBounds.height,
        },
        pageAspectRatio,
        imageAspectRatio,
      ),
    );
  };

  const endDrag = (event: PointerEvent<HTMLButtonElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    if (
      typeof event.currentTarget.hasPointerCapture === "function" &&
      event.currentTarget.hasPointerCapture(event.pointerId)
    ) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const moveWithKeyboard = (event: KeyboardEvent<HTMLButtonElement>) => {
    const movement = event.shiftKey ? 0.05 : 0.01;
    const offsets: Record<string, [number, number]> = {
      ArrowLeft: [-movement, 0],
      ArrowRight: [movement, 0],
      ArrowUp: [0, -movement],
      ArrowDown: [0, movement],
    };
    const offset = offsets[event.key];
    if (!offset) return;
    event.preventDefault();
    onPlacementChange(
      clampSignaturePlacement(
        { ...placement, x: placement.x + offset[0], y: placement.y + offset[1] },
        pageAspectRatio,
        imageAspectRatio,
      ),
    );
  };

  const height = signatureHeight(placement, pageAspectRatio, imageAspectRatio);
  const maxWidth = Math.max(0.02, Math.min(0.65, imageAspectRatio / pageAspectRatio));
  const minWidth = Math.min(0.06, maxWidth);

  return (
    <>
      {imageUrl ? (
        <div
          ref={overlayRef}
          className="signature-image-overlay"
          style={{
            left: `${placement.x * 100}%`,
            top: `${placement.y * 100}%`,
            width: `${placement.width * 100}%`,
            height: `${height * 100}%`,
          }}
        >
          <button
            type="button"
            className="signature-image-drag-surface"
            aria-label={t("signature.ready")}
            disabled={disabled}
            onPointerDown={beginDrag}
            onPointerMove={moveSignature}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
            onKeyDown={moveWithKeyboard}
          >
            <img
              src={imageUrl}
              alt=""
              draggable={false}
              onLoad={(event) => {
                const { naturalWidth, naturalHeight } = event.currentTarget;
                if (naturalWidth > 0 && naturalHeight > 0) {
                  const aspect = naturalWidth / naturalHeight;
                  setImageAspectRatio(aspect);
                  onPlacementChange(clampSignaturePlacement(placement, pageAspectRatio, aspect));
                }
              }}
            />
          </button>
          <SignatureResizeHandles
            overlayRef={overlayRef}
            placement={placement}
            pageAspectRatio={pageAspectRatio}
            imageAspectRatio={imageAspectRatio}
            disabled={disabled}
            onPlacementChange={onPlacementChange}
          />
        </div>
      ) : null}
      {imageUrl ? (
        <label className="signature-size-control">
          <span>{t("signature.sizeLabel")}</span>
          <input
            type="range"
            min={minWidth}
            max={maxWidth}
            step="0.01"
            value={Math.min(placement.width, maxWidth)}
            disabled={disabled}
            onChange={(event) => {
              onPlacementChange(
                resizeSignaturePlacement(
                  placement,
                  Number(event.currentTarget.value),
                  "bottomRight",
                  pageAspectRatio,
                  imageAspectRatio,
                ),
              );
            }}
          />
        </label>
      ) : null}
    </>
  );
}
