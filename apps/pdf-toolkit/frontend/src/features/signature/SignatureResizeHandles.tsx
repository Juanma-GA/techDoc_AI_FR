import { useRef, type KeyboardEvent, type PointerEvent, type RefObject } from "react";
import { useTranslation } from "react-i18next";

import {
  resizeSignaturePlacement,
  type ResizeCorner,
  type SignaturePlacement,
} from "./placement";
import { ResizeHandles } from "./ResizeHandles";

type SignatureResizeHandlesProps = {
  overlayRef: RefObject<HTMLDivElement | null>;
  placement: SignaturePlacement;
  pageAspectRatio: number;
  imageAspectRatio: number;
  disabled: boolean;
  onPlacementChange: (placement: SignaturePlacement) => void;
};

type ResizeState = {
  pointerId: number;
  corner: ResizeCorner;
  startX: number;
  startY: number;
  placement: SignaturePlacement;
  boxWidth: number;
  boxHeight: number;
};

export function SignatureResizeHandles({
  overlayRef,
  placement,
  pageAspectRatio,
  imageAspectRatio,
  disabled,
  onPlacementChange,
}: SignatureResizeHandlesProps) {
  const { t } = useTranslation();
  const resizeRef = useRef<ResizeState | null>(null);

  const beginResize = (corner: ResizeCorner, event: PointerEvent<HTMLButtonElement>) => {
    if (disabled || !overlayRef.current) return;
    event.preventDefault();
    event.stopPropagation();
    const bounds = overlayRef.current.getBoundingClientRect();
    resizeRef.current = {
      pointerId: event.pointerId,
      corner,
      startX: event.clientX,
      startY: event.clientY,
      placement,
      boxWidth: bounds.width,
      boxHeight: bounds.height,
    };
    if (typeof event.currentTarget.setPointerCapture === "function") {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  };

  const resize = (event: PointerEvent<HTMLButtonElement>) => {
    const drag = resizeRef.current;
    if (!drag || drag.pointerId !== event.pointerId || !drag.boxWidth || !drag.boxHeight) return;
    const horizontalScale =
      1 + (drag.corner.endsWith("Right") ? 1 : -1) * (event.clientX - drag.startX) / drag.boxWidth;
    const verticalScale =
      1 + (drag.corner.startsWith("bottom") ? 1 : -1) * (event.clientY - drag.startY) / drag.boxHeight;
    const scale = Math.max(0.1, (horizontalScale + verticalScale) / 2);
    onPlacementChange(
      resizeSignaturePlacement(
        drag.placement,
        drag.placement.width * scale,
        drag.corner,
        pageAspectRatio,
        imageAspectRatio,
      ),
    );
  };

  const endResize = (event: PointerEvent<HTMLButtonElement>) => {
    if (resizeRef.current?.pointerId !== event.pointerId) return;
    resizeRef.current = null;
    if (
      typeof event.currentTarget.hasPointerCapture === "function" &&
      event.currentTarget.hasPointerCapture(event.pointerId)
    ) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const resizeWithKeyboard = (corner: ResizeCorner, event: KeyboardEvent<HTMLButtonElement>) => {
    const step = event.shiftKey ? 0.05 : 0.01;
    const grows =
      (event.key === "ArrowRight" && corner.endsWith("Right")) ||
      (event.key === "ArrowLeft" && corner.endsWith("Left")) ||
      (event.key === "ArrowDown" && corner.startsWith("bottom")) ||
      (event.key === "ArrowUp" && corner.startsWith("top"));
    const shrinks =
      (event.key === "ArrowLeft" && corner.endsWith("Right")) ||
      (event.key === "ArrowRight" && corner.endsWith("Left")) ||
      (event.key === "ArrowUp" && corner.startsWith("bottom")) ||
      (event.key === "ArrowDown" && corner.startsWith("top"));
    if (!grows && !shrinks) return;
    event.preventDefault();
    onPlacementChange(
      resizeSignaturePlacement(
        placement,
        placement.width + (grows ? step : -step),
        corner,
        pageAspectRatio,
        imageAspectRatio,
      ),
    );
  };

  return (
    <ResizeHandles
      boxLabel={t("signature.resizeSignature")}
      disabled={disabled}
      onResizeStart={beginResize}
      onResizeMove={resize}
      onResizeEnd={endResize}
      onResizeKeyDown={resizeWithKeyboard}
    />
  );
}
