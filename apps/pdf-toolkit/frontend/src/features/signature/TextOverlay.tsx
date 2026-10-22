import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import { clampTextPlacement, type TextPlacement } from "./placement";

type TextOverlayProps = {
  text: string;
  label: string;
  pageRef: React.RefObject<HTMLDivElement | null>;
  pageViewportWidth: number;
  placement: TextPlacement;
  disabled: boolean;
  onPlacementChange: (placement: TextPlacement) => void;
};

type DragState = {
  pointerId: number;
  startX: number;
  startY: number;
  placement: TextPlacement;
};

const fontSizePoints = 14;

export function TextOverlay({
  text,
  label,
  pageRef,
  pageViewportWidth,
  placement,
  disabled,
  onPlacementChange,
}: TextOverlayProps) {
  const overlayRef = useRef<HTMLButtonElement>(null);
  const dragRef = useRef<DragState | null>(null);
  const [pageCssWidth, setPageCssWidth] = useState(0);

  useEffect(() => {
    const page = pageRef.current;
    if (!page) return;
    const updateWidth = () => setPageCssWidth(page.clientWidth);
    updateWidth();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(updateWidth);
    observer.observe(page);
    return () => observer.disconnect();
  }, [pageRef]);

  useEffect(() => {
    const pageBounds = pageRef.current?.getBoundingClientRect();
    const overlayBounds = overlayRef.current?.getBoundingClientRect();
    if (!pageBounds || !overlayBounds || pageBounds.width === 0 || pageBounds.height === 0) return;

    const clamped = clampTextPlacement(
      placement,
      overlayBounds.width / pageBounds.width,
      overlayBounds.height / pageBounds.height,
    );
    if (clamped.x !== placement.x || clamped.y !== placement.y) {
      onPlacementChange(clamped);
    }
  }, [onPlacementChange, pageCssWidth, pageRef, placement, text]);

  const beginDrag = (event: PointerEvent<HTMLButtonElement>) => {
    if (disabled || !pageRef.current || event.button !== 0) return;
    event.preventDefault();
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      placement,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const moveOverlay = (event: PointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    const pageBounds = pageRef.current?.getBoundingClientRect();
    const overlayBounds = event.currentTarget.getBoundingClientRect();
    if (!drag || drag.pointerId !== event.pointerId || !pageBounds || pageBounds.width === 0) return;

    onPlacementChange(
      clampTextPlacement(
        {
          x: drag.placement.x + (event.clientX - drag.startX) / pageBounds.width,
          y: drag.placement.y + (event.clientY - drag.startY) / pageBounds.height,
        },
        overlayBounds.width / pageBounds.width,
        overlayBounds.height / pageBounds.height,
      ),
    );
  };

  const endDrag = (event: PointerEvent<HTMLButtonElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
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
    const pageBounds = pageRef.current?.getBoundingClientRect();
    const overlayBounds = overlayRef.current?.getBoundingClientRect();
    if (!offset || !pageBounds || !overlayBounds) return;
    event.preventDefault();
    onPlacementChange(
      clampTextPlacement(
        { x: placement.x + offset[0], y: placement.y + offset[1] },
        overlayBounds.width / pageBounds.width,
        overlayBounds.height / pageBounds.height,
      ),
    );
  };

  return (
    <button
      ref={overlayRef}
      type="button"
      className="signature-text-overlay"
      style={{
        left: `${placement.x * 100}%`,
        top: `${placement.y * 100}%`,
        fontSize: `${
          pageCssWidth > 0 && pageViewportWidth > 0
            ? (fontSizePoints * 4 * pageCssWidth) / (3 * pageViewportWidth)
            : fontSizePoints
        }px`,
      }}
      aria-label={`${label}: ${text}`}
      disabled={disabled}
      onPointerDown={beginDrag}
      onPointerMove={moveOverlay}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onKeyDown={moveWithKeyboard}
    >
      {text}
    </button>
  );
}
