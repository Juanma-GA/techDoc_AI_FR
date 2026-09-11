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

/** Rectangle en pourcentages de la page (left/top/width/height en %). */
export type PercentRect = { left: number; top: number; width: number; height: number };

/**
 * Positionne une bbox en POURCENTAGES de l'image PNG rendue par PyMuPDF.
 * Les coordonnees de `search_for` restent dans le repere PDF non tourne, alors
 * que `get_pixmap` affiche la page dans son orientation (`page_rotation`).
 */
export function bboxToPercentRect(bbox: Bbox): PercentRect | null {
  if (!hasValidBbox(bbox)) return null;
  const pw = bbox.page_w ?? 0;
  const ph = bbox.page_h ?? 0;
  if (pw <= 0 || ph <= 0) return null;
  const x0 = bbox.x0 as number;
  const y0 = bbox.y0 as number;
  const x1 = bbox.x1 as number;
  const y1 = bbox.y1 as number;
  const minX = Math.min(x0, x1);
  const minY = Math.min(y0, y1);
  const maxX = Math.max(x0, x1);
  const maxY = Math.max(y0, y1);
  const rotation = ((bbox.page_rotation ?? 0) % 360 + 360) % 360;

  // For 90/270 degrees, page_w/page_h are already swapped by PyMuPDF's
  // displayed page rect, so recover the unrotated dimensions from them.
  const sourceWidth = rotation === 90 || rotation === 270 ? ph : pw;
  const sourceHeight = rotation === 90 || rotation === 270 ? pw : ph;
  let left = minX;
  let top = minY;
  let width = maxX - minX;
  let height = maxY - minY;

  if (rotation === 90) {
    left = sourceHeight - maxY;
    top = minX;
    width = maxY - minY;
    height = maxX - minX;
  } else if (rotation === 180) {
    left = sourceWidth - maxX;
    top = sourceHeight - maxY;
  } else if (rotation === 270) {
    left = minY;
    top = sourceWidth - maxX;
    width = maxY - minY;
    height = maxX - minX;
  }

  return {
    left: (left / pw) * 100,
    top: (top / ph) * 100,
    width: (width / pw) * 100,
    height: (height / ph) * 100,
  };
}

export function hasValidBbox(bbox: Bbox): boolean {
  return (
    typeof bbox.x0 === "number" && typeof bbox.y0 === "number" &&
    typeof bbox.x1 === "number" && typeof bbox.y1 === "number"
  );
}

export function bboxToCssRect(bbox: Bbox, viewport: ViewportLike, dpr = 1): CssRect {
  if (!hasValidBbox(bbox)) return { left: 0, top: 0, width: 0, height: 0 };
  // Defensif : un viewport mal forme (mauvaise version pdf.js, page proxy passe
  // a la place du viewport...) ne doit pas crasher toute l'UI — on degrade en
  // "pas de surlignage" plutot que de lever dans le rendu React.
  if (typeof viewport?.convertToViewportRectangle !== "function") {
    return { left: 0, top: 0, width: 0, height: 0 };
  }
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
