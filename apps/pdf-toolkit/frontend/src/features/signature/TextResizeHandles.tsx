import { useRef, type KeyboardEvent, type PointerEvent, type RefObject } from "react";

import { resizeTextPlacement, type ResizeCorner, type TextPlacement } from "./placement";
import { ResizeHandles } from "./ResizeHandles";

type TextResizeHandlesProps = {
  boxLabel: string;
  overlayRef: RefObject<HTMLDivElement | null>;
  pageRef: RefObject<HTMLDivElement | null>;
  placement: TextPlacement;
  disabled: boolean;
  onPlacementChange: (placement: TextPlacement) => void;
};

type ResizeState = {
  pointerId: number;
  corner: ResizeCorner;
  startX: number;
  startY: number;
  placement: TextPlacement;
  boxWidth: number;
  boxHeight: number;
};

export function TextResizeHandles({
  boxLabel,
  overlayRef,
  pageRef,
  placement,
  disabled,
  onPlacementChange,
}: TextResizeHandlesProps) {
  const resizeRef = useRef<ResizeState | null>(null);

  const beginResize = (corner: ResizeCorner, event: PointerEvent<HTMLButtonElement>) => {
    if (disabled || !overlayRef.current || !pageRef.current) return;
    event.preventDefault();
    event.stopPropagation();
    const overlayBounds = overlayRef.current.getBoundingClientRect();
    const pageBounds = pageRef.current.getBoundingClientRect();
    if (pageBounds.width === 0 || pageBounds.height === 0) return;
    resizeRef.current = {
      pointerId: event.pointerId,
      corner,
      startX: event.clientX,
      startY: event.clientY,
      placement,
      boxWidth: overlayBounds.width / pageBounds.width,
      boxHeight: overlayBounds.height / pageBounds.height,
    };
    if (typeof event.currentTarget.setPointerCapture === "function") {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  };

  const resize = (event: PointerEvent<HTMLButtonElement>) => {
    const drag = resizeRef.current;
    if (!drag || drag.pointerId !== event.pointerId || !drag.boxWidth || !drag.boxHeight) return;
    const scaleX =
      1 + (drag.corner.endsWith("Right") ? 1 : -1) * (event.clientX - drag.startX) /
        (drag.boxWidth * (pageRef.current?.clientWidth ?? 1));
    const scaleY =
      1 + (drag.corner.startsWith("bottom") ? 1 : -1) * (event.clientY - drag.startY) /
        (drag.boxHeight * (pageRef.current?.clientHeight ?? 1));
    const scale = Math.max(0.25, (scaleX + scaleY) / 2);
    onPlacementChange(
      resizeTextPlacement(
        drag.placement,
        drag.placement.fontSize * scale,
        drag.corner,
        drag.boxWidth,
        drag.boxHeight,
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
    const step = event.shiftKey ? 4 : 1;
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
    const pageBounds = pageRef.current?.getBoundingClientRect();
    const overlayBounds = overlayRef.current?.getBoundingClientRect();
    if (
      (!grows && !shrinks) ||
      !pageBounds ||
      !overlayBounds ||
      pageBounds.width === 0 ||
      pageBounds.height === 0
    ) {
      return;
    }
    event.preventDefault();
    onPlacementChange(
      resizeTextPlacement(
        placement,
        placement.fontSize + (grows ? step : -step),
        corner,
        overlayBounds.width / pageBounds.width,
        overlayBounds.height / pageBounds.height,
      ),
    );
  };

  return (
    <ResizeHandles
      boxLabel={boxLabel}
      disabled={disabled}
      onResizeStart={beginResize}
      onResizeMove={resize}
      onResizeEnd={endResize}
      onResizeKeyDown={resizeWithKeyboard}
    />
  );
}
