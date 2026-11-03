import type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist";

export type CropMode = "manual" | "automatic";

export type CropRegion = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};

export type PageCropRect = {
  page: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

export type CropAnalysisResult = {
  rectangles: PageCropRect[];
  changedPages: number;
};

export type CropAnalysisProgress = (completed: number, total: number) => void;
type CropViewport = Pick<
  ReturnType<PDFPageProxy["getViewport"]>,
  "width" | "height" | "convertToPdfPoint"
>;

const FULL_PAGE: CropRegion = { left: 0, top: 0, right: 1, bottom: 1 };
const WHITE_THRESHOLD = 250;
const MAX_RENDER_SIZE = 1200;

export function detectVisibleBounds(
  pixels: Uint8ClampedArray,
  width: number,
  height: number,
): CropRegion | null {
  if (width < 1 || height < 1 || pixels.length < width * height * 4) {
    throw new RangeError("Invalid rendered page pixels");
  }

  let minX = width;
  let minY = height;
  let maxX = -1;
  let maxY = -1;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const offset = (y * width + x) * 4;
      const alpha = pixels[offset + 3] ?? 0;
      const red = pixels[offset] ?? 255;
      const green = pixels[offset + 1] ?? 255;
      const blue = pixels[offset + 2] ?? 255;
      if (alpha > 0 && (red < WHITE_THRESHOLD || green < WHITE_THRESHOLD || blue < WHITE_THRESHOLD)) {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
    }
  }

  if (maxX < minX || maxY < minY) return null;

  const padding = Math.max(3, Math.ceil(Math.min(width, height) * 0.015));
  return {
    left: Math.max(0, minX - padding) / width,
    top: Math.max(0, minY - padding) / height,
    right: Math.min(width, maxX + 1 + padding) / width,
    bottom: Math.min(height, maxY + 1 + padding) / height,
  };
}

export async function buildPageCropRectangles(
  documentProxy: PDFDocumentProxy,
  mode: CropMode,
  manualRegion: CropRegion | null,
  signal: AbortSignal,
  onProgress: CropAnalysisProgress,
): Promise<CropAnalysisResult> {
  if (mode === "manual" && !manualRegion) {
    throw new Error("A manual crop region is required");
  }

  const rectangles: PageCropRect[] = [];
  let changedPages = 0;
  const canvas = mode === "automatic" ? document.createElement("canvas") : null;

  try {
    for (let pageNumber = 1; pageNumber <= documentProxy.numPages; pageNumber++) {
      throwIfAborted(signal);
      const page = await documentProxy.getPage(pageNumber);
      try {
        let region = manualRegion ?? FULL_PAGE;
        if (mode === "automatic") {
          if (!canvas) throw new Error("The page analysis canvas is unavailable");
          region = await detectPageBounds(page, canvas, signal) ?? FULL_PAGE;
        }
        if (hasRemovableMargins(region)) changedPages++;
        rectangles.push(pageCropRectFromRegion(page, pageNumber, region));
        onProgress(pageNumber, documentProxy.numPages);
      } finally {
        page.cleanup();
      }
    }
  } finally {
    if (canvas) {
      canvas.width = 0;
      canvas.height = 0;
    }
  }
  return { rectangles, changedPages };
}

function pageCropRectFromRegion(
  page: PDFPageProxy,
  pageNumber: number,
  region: CropRegion,
): PageCropRect {
  return pdfCropRectFromRegion(pageNumber, page.getViewport({ scale: 1 }), region);
}

export function pdfCropRectFromRegion(
  pageNumber: number,
  viewport: CropViewport,
  region: CropRegion,
): PageCropRect {
  const [firstX, firstY] = viewport.convertToPdfPoint(
    region.left * viewport.width,
    region.top * viewport.height,
  );
  const [secondX, secondY] = viewport.convertToPdfPoint(
    region.right * viewport.width,
    region.bottom * viewport.height,
  );
  return {
    page: pageNumber,
    x1: Math.min(firstX, secondX),
    y1: Math.min(firstY, secondY),
    x2: Math.max(firstX, secondX),
    y2: Math.max(firstY, secondY),
  };
}

async function detectPageBounds(
  page: PDFPageProxy,
  canvas: HTMLCanvasElement,
  signal: AbortSignal,
): Promise<CropRegion | null> {
  const naturalViewport = page.getViewport({ scale: 1 });
  const scale = Math.min(1, MAX_RENDER_SIZE / Math.max(naturalViewport.width, naturalViewport.height));
  const viewport = page.getViewport({ scale });
  canvas.width = Math.max(1, Math.ceil(viewport.width));
  canvas.height = Math.max(1, Math.ceil(viewport.height));
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("The page analysis canvas is unavailable");

  const renderTask = page.render({
    canvasContext: context,
    viewport,
    background: "white",
  });
  const cancelRender = () => renderTask.cancel();
  signal.addEventListener("abort", cancelRender, { once: true });
  try {
    await renderTask.promise;
    throwIfAborted(signal);
    return detectVisibleBounds(
      context.getImageData(0, 0, canvas.width, canvas.height).data,
      canvas.width,
      canvas.height,
    );
  } finally {
    signal.removeEventListener("abort", cancelRender);
    context.clearRect(0, 0, canvas.width, canvas.height);
  }
}

function hasRemovableMargins(region: CropRegion): boolean {
  const tolerance = 0.005;
  return (
    region.left > tolerance ||
    region.top > tolerance ||
    region.right < 1 - tolerance ||
    region.bottom < 1 - tolerance
  );
}

function throwIfAborted(signal: AbortSignal): void {
  if (signal.aborted) {
    throw signal.reason ?? new DOMException("Crop analysis cancelled", "AbortError");
  }
}
