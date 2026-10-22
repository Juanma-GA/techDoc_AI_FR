export type SignaturePlacement = {
  x: number;
  y: number;
  width: number;
};

export type TextPlacement = {
  x: number;
  y: number;
};

export const defaultSignaturePlacement: SignaturePlacement = {
  x: 0.36,
  y: 0.72,
  width: 0.28,
};

export const defaultNamePlacement: TextPlacement = { x: 0.12, y: 0.87 };
export const defaultDatePlacement: TextPlacement = { x: 0.12, y: 0.92 };

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
    x: clamp(placement.x, 0, Math.max(0, 1 - boxWidth)),
    y: clamp(placement.y, 0, Math.max(0, Math.min(0.95, 1 - boxHeight))),
  };
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}
