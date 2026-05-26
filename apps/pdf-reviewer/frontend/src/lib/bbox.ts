/**
 * Convert a PDF-points bbox (PyMuPDF) into a CSS rectangle inside a
 * react-pdf <Page> render container, using the viewport reported by
 * pdfjs at `onRenderSuccess` time.
 *
 * Backend bboxes are in top-left origin PDF points. pdfjs viewport's
 * `convertToViewportRectangle([x0, y0, x1, y1])` yields canvas pixels.
 * We divide by `devicePixelRatio` to get CSS pixels.
 */

export type Bbox = {
  x0: number | null;
  y0: number | null;
  x1: number | null;
  y1: number | null;
  page_w?: number;
  page_h?: number;
  page_rotation?: number;
};

export type ViewportLike = {
  convertToViewportRectangle(rect: [number, number, number, number]): [number, number, number, number];
};

export type CssRect = { left: number; top: number; width: number; height: number };

export function hasValidBbox(bbox: Bbox): boolean {
  return (
    typeof bbox.x0 === "number" && typeof bbox.y0 === "number" &&
    typeof bbox.x1 === "number" && typeof bbox.y1 === "number"
  );
}

export function bboxToCssRect(bbox: Bbox, viewport: ViewportLike, dpr = 1): CssRect {
  if (!hasValidBbox(bbox)) return { left: 0, top: 0, width: 0, height: 0 };
  const [vx0, vy0, vx1, vy1] = viewport.convertToViewportRectangle([
    bbox.x0 as number,
    bbox.y0 as number,
    bbox.x1 as number,
    bbox.y1 as number,
  ]);
  const left = Math.min(vx0, vx1) / dpr;
  const top = Math.min(vy0, vy1) / dpr;
  const width = Math.abs(vx1 - vx0) / dpr;
  const height = Math.abs(vy1 - vy0) / dpr;
  return { left, top, width, height };
}
