import type { TFunction } from "i18next";
import { useCallback, useRef, useState } from "react";
import type { PointerEvent, SyntheticEvent } from "react";

import { imageReplaceApi } from "../lib/api";
import { fillWithDetectedBackground } from "../lib/image-processing";

export const MIN_BRUSH_SIZE = 8;
export const MAX_BRUSH_SIZE = 80;

type ImageBrushOptions = {
  imageFile: File | null;
  previewImage: string;
  hasProcessedPreview: boolean;
  onImageEdited: (image: string) => void;
  t: TFunction;
};

export function useImageBrush({
  imageFile,
  previewImage,
  hasProcessedPreview,
  onImageEdited,
  t,
}: ImageBrushOptions) {
  const [eraseMode, setEraseMode] = useState<"lama" | "color">("lama");
  const [brushEnabled, setBrushEnabled] = useState(false);
  const [brushSize, setBrushSize] = useState(28);
  const [hasBrushMask, setHasBrushMask] = useState(false);
  const [inpainting, setInpainting] = useState(false);
  const [inpaintError, setInpaintError] = useState("");
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const painting = useRef(false);

  function prepareCanvas(event: SyntheticEvent<HTMLImageElement>) {
    const image = event.currentTarget;
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    setHasBrushMask(false);
  }

  function brushPosition(event: PointerEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    return {
      x: (event.clientX - rect.left) * (canvas.width / rect.width),
      y: (event.clientY - rect.top) * (canvas.height / rect.height),
      scale: canvas.width / rect.width,
    };
  }

  function startBrush(event: PointerEvent<HTMLCanvasElement>) {
    event.preventDefault();
    event.stopPropagation();
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    const position = brushPosition(event);
    if (!canvas || !context || !position) return;

    painting.current = true;
    canvas.setPointerCapture(event.pointerId);
    context.lineCap = "round";
    context.lineJoin = "round";
    context.lineWidth = brushSize * position.scale;
    context.strokeStyle = getComputedStyle(document.documentElement)
      .getPropertyValue("--color-semantic-danger")
      .trim();
    context.globalAlpha = 0.6;
    context.beginPath();
    context.moveTo(position.x, position.y);
    context.lineTo(position.x + 0.01, position.y + 0.01);
    context.stroke();
    context.globalAlpha = 1;
    setHasBrushMask(true);
  }

  function moveBrush(event: PointerEvent<HTMLCanvasElement>) {
    if (!painting.current) return;
    const context = canvasRef.current?.getContext("2d");
    const position = brushPosition(event);
    if (!context || !position) return;

    context.lineWidth = brushSize * position.scale;
    context.globalAlpha = 0.6;
    context.lineTo(position.x, position.y);
    context.stroke();
    context.globalAlpha = 1;
    context.beginPath();
    context.moveTo(position.x, position.y);
  }

  function stopBrush(event: PointerEvent<HTMLCanvasElement>) {
    if (!painting.current) return;
    painting.current = false;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function clearBrushMask() {
    painting.current = false;
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (canvas && context) context.clearRect(0, 0, canvas.width, canvas.height);
    setHasBrushMask(false);
  }

  const resetBrush = useCallback(() => {
    setBrushEnabled(false);
    setHasBrushMask(false);
    setInpaintError("");
    painting.current = false;
  }, []);

  async function applyBrush() {
    const canvas = canvasRef.current;
    if (!imageFile || !canvas || !hasBrushMask || inpainting) return;

    setInpainting(true);
    setInpaintError("");
    try {
      const maskBlob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, "image/png"),
      );
      if (!maskBlob) throw new Error(t("image.errorMask"));

      const imageBlob = hasProcessedPreview
        ? await (await fetch(previewImage)).blob()
        : imageFile;
      if (eraseMode === "color") {
        onImageEdited(await fillWithDetectedBackground(imageBlob, canvas, t));
      } else {
        const formData = new FormData();
        formData.append("image", imageBlob, imageBlob.type === "image/jpeg" ? "image.jpg" : "image.png");
        formData.append("mask", maskBlob, "mask.png");
        const payload = await imageReplaceApi.inpaint(formData);
        onImageEdited(payload.edited_image);
      }
      setBrushEnabled(false);
      clearBrushMask();
    } catch (requestError) {
      setInpaintError(requestError instanceof Error ? requestError.message : t("image.errorGeneric"));
    } finally {
      setInpainting(false);
    }
  }

  return {
    eraseMode,
    setEraseMode,
    brushEnabled,
    setBrushEnabled,
    brushSize,
    setBrushSize,
    hasBrushMask,
    inpainting,
    inpaintError,
    canvasRef,
    prepareCanvas,
    startBrush,
    moveBrush,
    stopBrush,
    clearBrushMask,
    applyBrush,
    resetBrush,
  };
}
