export type SignaturePlacement = {
  x: number;
  y: number;
  width: number;
};

export type TextPlacement = {
  x: number;
  y: number;
  fontSize: number;
};

export type ResizeCorner = "topLeft" | "topRight" | "bottomLeft" | "bottomRight";

export const defaultSignaturePlacement: SignaturePlacement = {
  x: 0.36,
  y: 0.72,
  width: 0.28,
};

export const defaultTextFontSize = 14;
export const defaultNamePlacement: TextPlacement = { x: 0.12, y: 0.87, fontSize: defaultTextFontSize };
export const defaultDatePlacement: TextPlacement = { x: 0.12, y: 0.92, fontSize: defaultTextFontSize };

export function clampSignaturePlacement(
  placement: SignaturePlacement,
  pageAspectRatio: number,
  imageAspectRatio: number,
): SignaturePlacement {
  const safePageAspect = Number.isFinite(pageAspectRatio) && pageAspectRatio > 0 ? pageAspectRatio : 1;
  const safeImageAspect = Number.isFinite(imageAspectRatio) && imageAspectRatio > 0 ? imageAspectRatio : 1;
  const width = Math.max(0, Math.min(1, placement.width));
  const height = Math.min(1, (width * safePageAspect) / safeImageAspect);
  return {
    x: clamp(placement.x, 0, 1 - width),
    y: clamp(placement.y, 0, 1 - height),
    width,
  };
}

export function signatureHeight(
  placement: SignaturePlacement,
  pageAspectRatio: number,
  imageAspectRatio: number,
): number {
  if (!Number.isFinite(pageAspectRatio) || pageAspectRatio <= 0) return placement.width;
  if (!Number.isFinite(imageAspectRatio) || imageAspectRatio <= 0) return placement.width;
  return (placement.width * pageAspectRatio) / imageAspectRatio;
}

export function clampTextPlacement(
  placement: TextPlacement,
  boxWidth: number,
  boxHeight: number,
): TextPlacement {
  return {
    fontSize: placement.fontSize,
    x: clamp(placement.x, 0, Math.max(0, 1 - boxWidth)),
    y: clamp(placement.y, 0, Math.max(0, Math.min(0.95, 1 - boxHeight))),
  };
}

export function resizeSignaturePlacement(
  placement: SignaturePlacement,
  width: number,
  corner: ResizeCorner,
  pageAspectRatio: number,
  imageAspectRatio: number,
): SignaturePlacement {
  const maxWidth = Math.max(0.02, Math.min(0.65, imageAspectRatio / pageAspectRatio));
  const minWidth = Math.min(0.06, maxWidth);
  const resizedWidth = clamp(width, minWidth, maxWidth);
  const oldHeight = signatureHeight(placement, pageAspectRatio, imageAspectRatio);
  const newHeight = signatureHeight(
    { ...placement, width: resizedWidth },
    pageAspectRatio,
    imageAspectRatio,
  );
  return clampSignaturePlacement(
    {
      x: corner.endsWith("Right") ? placement.x : placement.x + placement.width - resizedWidth,
      y: corner.startsWith("bottom") ? placement.y : placement.y + oldHeight - newHeight,
      width: resizedWidth,
    },
    pageAspectRatio,
    imageAspectRatio,
  );
}

export function resizeTextPlacement(
  placement: TextPlacement,
  fontSize: number,
  corner: ResizeCorner,
  boxWidth: number,
  boxHeight: number,
): TextPlacement {
  const resizedFontSize = clamp(Math.round(fontSize), 6, 48);
  const scale = placement.fontSize > 0 ? resizedFontSize / placement.fontSize : 1;
  const width = boxWidth * scale;
  const height = boxHeight * scale;
  return clampTextPlacement(
    {
      fontSize: resizedFontSize,
      x: corner.endsWith("Right") ? placement.x : placement.x + boxWidth - width,
      y: corner.startsWith("bottom") ? placement.y : placement.y + boxHeight - height,
    },
    width,
    height,
  );
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}
