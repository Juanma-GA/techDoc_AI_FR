import type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist";
import type { TextItem } from "pdfjs-dist/types/src/display/api";

import type { SplitZone } from "./splitModel";

type PositionedText = { text: string; left: number; top: number; height: number };

/** Reads the text whose glyphs fall inside the zone (fractions of the displayed page, top-left origin). */
export async function readZoneText(page: PDFPageProxy, zone: SplitZone): Promise<string> {
  const viewport = page.getViewport({ scale: 1 });
  const content = await page.getTextContent();
  const fragments: PositionedText[] = [];

  for (const item of content.items) {
    if (!("str" in item) || !item.str.trim()) continue;
    const fragment = clipItemToZone(item, zone, viewport.width, viewport.height, (x, y) =>
      viewport.convertToViewportPoint(x, y) as [number, number],
    );
    if (fragment) fragments.push(fragment);
  }

  fragments.sort((left, right) => left.top - right.top || left.left - right.left);
  const lines: PositionedText[][] = [];
  for (const fragment of fragments) {
    const line = lines[lines.length - 1];
    const reference = line?.[0];
    if (line && reference && Math.abs(reference.top - fragment.top) <= Math.max(reference.height, fragment.height) * 0.5) {
      line.push(fragment);
    } else {
      lines.push([fragment]);
    }
  }
  return lines
    .map((line) =>
      line
        .sort((left, right) => left.left - right.left)
        .map((fragment) => fragment.text)
        .join(" "),
    )
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

function clipItemToZone(
  item: TextItem,
  zone: SplitZone,
  pageWidth: number,
  pageHeight: number,
  toViewport: (x: number, y: number) => [number, number],
): PositionedText | null {
  const [, b, c, , e, f] = item.transform as number[];
  const height = item.height || Math.hypot(item.transform[2] ?? 0, item.transform[3] ?? 0) || 1;
  const corners = [
    toViewport(e ?? 0, f ?? 0),
    toViewport((e ?? 0) + item.width, (f ?? 0) + height),
  ];
  const xs = corners.map(([x]) => x / pageWidth);
  const ys = corners.map(([, y]) => y / pageHeight);
  const left = Math.min(...xs);
  const right = Math.max(...xs);
  const top = Math.min(...ys);
  const bottom = Math.max(...ys);
  const zoneRight = zone.x + zone.width;
  const zoneBottom = zone.y + zone.height;

  const centerY = (top + bottom) / 2;
  if (centerY < zone.y || centerY > zoneBottom || right < zone.x || left > zoneRight) return null;

  const upright = Math.abs(b ?? 0) < 1e-6 && Math.abs(c ?? 0) < 1e-6;
  const characters = Array.from(item.str);
  if (!upright || characters.length < 2 || right - left <= 0) {
    const centerX = (left + right) / 2;
    if (centerX < zone.x || centerX > zoneRight) return null;
    return { text: item.str, left, top, height: bottom - top };
  }

  // Keep only the characters whose estimated centre lies in the zone (uniform width approximation).
  const step = (right - left) / characters.length;
  const kept = characters.filter((_, index) => {
    const center = left + step * (index + 0.5);
    return center >= zone.x && center <= zoneRight;
  });
  const text = kept.join("").trim();
  return text ? { text, left: Math.max(left, zone.x), top, height: bottom - top } : null;
}

/** Reads the zone text on every page of an already opened document; index 0 = page 1. */
export async function readZoneTextsForDocument(
  documentProxy: PDFDocumentProxy,
  zone: SplitZone,
  onProgress: (completed: number, total: number) => void,
  signal: AbortSignal,
): Promise<string[]> {
  const texts: string[] = [];
  onProgress(0, documentProxy.numPages);
  for (let pageNumber = 1; pageNumber <= documentProxy.numPages; pageNumber += 1) {
    if (signal.aborted) throw new DOMException("Detection cancelled", "AbortError");
    const page = await documentProxy.getPage(pageNumber);
    texts.push(await readZoneText(page, zone));
    onProgress(pageNumber, documentProxy.numPages);
  }
  return texts;
}
