import { useCallback, useRef, useState } from "react";
import type { PointerEvent } from "react";

const MAX_ZOOM = 4;
const ZOOM_STEP = 0.25;

export function useImageView(brushEnabled: boolean) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const previewElement = useRef<HTMLDivElement | null>(null);
  const zoomRef = useRef(1);
  const panStart = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);

  const setZoomLevel = useCallback((nextZoom: number) => {
    const next = Math.max(1, Math.min(MAX_ZOOM, nextZoom));
    zoomRef.current = next;
    setZoom(next);
    if (next === 1) setPan({ x: 0, y: 0 });
  }, []);

  const handleWheel = useCallback((event: WheelEvent) => {
    event.preventDefault();
    setZoomLevel(zoomRef.current + (event.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP));
  }, [setZoomLevel]);

  const previewRef = useCallback((element: HTMLDivElement | null) => {
    if (previewElement.current) {
      previewElement.current.removeEventListener("wheel", handleWheel);
    }
    previewElement.current = element;
    if (element) {
      element.addEventListener("wheel", handleWheel, { passive: false });
    }
  }, [handleWheel]);

  function startPan(event: PointerEvent<HTMLDivElement>) {
    if (brushEnabled || zoom === 1 || event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    panStart.current = {
      x: event.clientX,
      y: event.clientY,
      panX: pan.x,
      panY: pan.y,
    };
    setDragging(true);
  }

  function movePan(event: PointerEvent<HTMLDivElement>) {
    const start = panStart.current;
    const viewport = previewElement.current;
    if (!start || !viewport) return;

    const maxX = (viewport.clientWidth * (zoom - 1)) / 2;
    const maxY = (viewport.clientHeight * (zoom - 1)) / 2;
    setPan({
      x: Math.max(-maxX, Math.min(maxX, start.panX + event.clientX - start.x)),
      y: Math.max(-maxY, Math.min(maxY, start.panY + event.clientY - start.y)),
    });
  }

  function stopPan(event: PointerEvent<HTMLDivElement>) {
    if (!panStart.current) return;
    panStart.current = null;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  const resetView = useCallback(() => {
    panStart.current = null;
    setDragging(false);
    setPan({ x: 0, y: 0 });
    zoomRef.current = 1;
    setZoom(1);
  }, []);

  return {
    zoom,
    pan,
    dragging,
    previewRef,
    setZoomLevel,
    startPan,
    movePan,
    stopPan,
    resetView,
  };
}
