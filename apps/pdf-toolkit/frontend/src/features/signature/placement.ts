export type SignaturePlacement = {
  x: number;
  y: number;
  width: number;
};

export const defaultSignaturePlacement: SignaturePlacement = {
  x: 0.36,
  y: 0.76,
  width: 0.28,
};

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

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}
