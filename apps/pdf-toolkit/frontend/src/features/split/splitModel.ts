export type SplitRow = {
  id: string;
  pages: string;
  value: string;
};

export type SplitZone = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type ValueType = "text" | "number" | "code" | "regex";
export type SearchScope = "zone" | "page";
export type GroupingMode = "change" | "same";
export type MissingValueMode = "previous" | "skip";

export const defaultZone: SplitZone = { x: 0.6, y: 0.03, width: 0.35, height: 0.08 };
export const fullPageZone: SplitZone = { x: 0, y: 0, width: 1, height: 1 };
export const defaultNamePattern = "{nom}_{valeur}";
export const maxSplitGroups = 1000;

const maxNameLength = 150;
const reservedNames = new Set([
  "CON",
  "PRN",
  "AUX",
  "NUL",
  ...Array.from({ length: 9 }, (_, index) => `COM${index + 1}`),
  ...Array.from({ length: 9 }, (_, index) => `LPT${index + 1}`),
]);

let rowCounter = 0;

export function createRow(pages = "", value = ""): SplitRow {
  rowCounter += 1;
  return { id: `row-${rowCounter}`, pages, value };
}

/** Returns the selected pages, or null when the selection is invalid for the document. */
export function parsePageSelection(selection: string, pageCount: number): number[] | null {
  const trimmed = selection.trim();
  if (!trimmed || pageCount < 1) return null;
  const pages: number[] = [];
  const seen = new Set<number>();
  for (const term of trimmed.split(",")) {
    const bounds = term.trim().split("-").map((bound) => bound.trim());
    if (bounds.length > 2 || bounds.some((bound) => !/^\d+$/.test(bound))) return null;
    const first = Number(bounds[0]);
    const last = Number(bounds[1] ?? bounds[0]);
    if (first < 1 || first > last || last > pageCount) return null;
    for (let page = first; page <= last; page += 1) {
      if (seen.has(page)) return null;
      seen.add(page);
      pages.push(page);
    }
  }
  return pages;
}

/** Formats page numbers as a compact selection, e.g. [1,2,3,5] -> "1-3,5". */
export function formatPageSelection(pages: number[]): string {
  const sorted = [...new Set(pages)].sort((left, right) => left - right);
  const ranges: string[] = [];
  let index = 0;
  while (index < sorted.length) {
    const start = sorted[index] as number;
    let end = start;
    while (sorted[index + 1] === end + 1) {
      end += 1;
      index += 1;
    }
    ranges.push(start === end ? `${start}` : `${start}-${end}`);
    index += 1;
  }
  return ranges.join(",");
}

/** Builds rows of `chunkSize` consecutive pages with empty values. */
export function chunkRows(pageCount: number, chunkSize: number): SplitRow[] {
  const size = Math.max(1, Math.floor(chunkSize));
  const rows: SplitRow[] = [];
  for (let first = 1; first <= pageCount; first += size) {
    const last = Math.min(pageCount, first + size - 1);
    rows.push(createRow(first === last ? `${first}` : `${first}-${last}`));
  }
  return rows;
}

/** Semicolons or newlines separate documents; commas combine pages within one document. */
export function parseSplitRanges(text: string, pageCount: number): string[] | null {
  const ranges = text.split(/[;\r\n]+/).map((range) => range.trim()).filter(Boolean);
  if (ranges.length === 0 || ranges.length > maxSplitGroups) return null;
  return ranges.every((range) => parsePageSelection(range, pageCount) !== null) ? ranges : null;
}

/**
 * Parses pasted lines "pages;value" (also tab-separated from spreadsheets or "|").
 * Returns valid rows and the 1-based numbers of rejected lines.
 */
export function parsePastedRows(text: string): { rows: SplitRow[]; rejected: number[] } {
  const rows: SplitRow[] = [];
  const rejected: number[] = [];
  text.split(/\r?\n/).forEach((line, index) => {
    if (!line.trim()) return;
    const match = /^\s*([\d\s,-]+?)\s*[;\t|]\s*(.*)$/.exec(line);
    if (!match?.[1] || !/\d/.test(match[1])) {
      rejected.push(index + 1);
      return;
    }
    rows.push(createRow(match[1].replace(/\s+/g, ""), (match[2] ?? "").trim()));
  });
  return { rows, rejected };
}

/** Throws a SyntaxError when the custom regular expression is invalid. */
export function buildValuePattern(valueType: ValueType, customPattern: string): RegExp | null {
  switch (valueType) {
    case "text":
      return null;
    case "number":
      return /\d+(?:[.,]\d+)*/;
    case "code":
      return /[\p{L}\p{N}](?:[\p{L}\p{N}._/-]*[\p{L}\p{N}])?/u;
    case "regex":
      return new RegExp(customPattern, "u");
  }
}

/** Extracts the typed value from the text read in the zone; returns "" when nothing matches. */
export function extractValue(text: string, pattern: RegExp | null): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!pattern) return normalized;
  const match = pattern.exec(normalized);
  if (!match) return "";
  const captured = match.slice(1).find((group) => group !== undefined && group !== "");
  return (captured ?? match[0]).trim();
}

type PageGroup = { value: string; pages: number[] };

/** Groups per-page values (index 0 = page 1) into split rows. */
export function groupPageValues(
  values: string[],
  grouping: GroupingMode,
  missing: MissingValueMode,
): { rows: SplitRow[]; missingPages: number[] } {
  const groups: PageGroup[] = [];
  const missingPages: number[] = [];
  let current: PageGroup | null = null;

  values.forEach((rawValue, index) => {
    const page = index + 1;
    const value = rawValue.trim();
    if (!value) {
      missingPages.push(page);
      if (missing === "skip") return;
      if (current) {
        current.pages.push(page);
      } else {
        current = { value: "", pages: [page] };
        groups.push(current);
      }
      return;
    }
    if (current?.value === value) {
      current.pages.push(page);
      return;
    }
    if (current && current.value === "") {
      // Leading pages without value join the first detected document.
      current.value = value;
      current.pages.push(page);
      return;
    }
    const existing = grouping === "same" ? groups.find((group) => group.value === value) : undefined;
    if (existing) {
      existing.pages.push(page);
      current = existing;
      return;
    }
    current = { value, pages: [page] };
    groups.push(current);
  });

  return {
    rows: groups.map((group) => createRow(formatPageSelection(group.pages), group.value)),
    missingPages,
  };
}

export type NameContext = {
  value: string;
  index: number;
  pages: string;
  sourceName: string;
  total: number;
};

/** Replaces {valeur}/{value}, {n}, {pages} and {nom}/{name} in the file name pattern. */
export function applyNamePattern(pattern: string, context: NameContext): string {
  const width = Math.max(2, String(context.total).length);
  const replacements: Record<string, string> = {
    valeur: context.value,
    value: context.value,
    n: String(context.index).padStart(width, "0"),
    pages: context.pages,
    nom: context.sourceName,
    name: context.sourceName,
  };
  return pattern.replace(/\{(valeur|value|n|pages|nom|name)\}/gi, (_, token: string) => {
    return replacements[token.toLowerCase()] ?? "";
  });
}

/** Mirrors the backend sanitizer so the preview matches the generated file names. */
export function sanitizeBaseName(name: string): string {
  let base = name.trim();
  if (base.toLowerCase().endsWith(".pdf")) base = base.slice(0, -4);
  base = Array.from(base)
    .map((character) => (/[\p{L}\p{Nd} \-_.()[\]+,&'#=@]/u.test(character) ? character : "_"))
    .join("");
  base = trimNameEdges(base);
  const characters = Array.from(base);
  if (characters.length > maxNameLength) {
    base = trimNameEdges(characters.slice(0, maxNameLength).join(""));
  }
  if (!base) return "";
  const stem = (base.split(".")[0] ?? "").trim().toUpperCase();
  return reservedNames.has(stem) ? `_${base}` : base;
}

export function uniqueFileNames(names: string[]): string[] {
  const used = new Set<string>();
  return names.map((name, index) => {
    const base = sanitizeBaseName(name) || `document-${index + 1}`;
    let candidate = base;
    for (let suffix = 2; used.has(candidate.toLowerCase()); suffix += 1) {
      candidate = `${base}_${suffix}`;
    }
    used.add(candidate.toLowerCase());
    return `${candidate}.pdf`;
  });
}

export function sourceBaseName(fileName: string): string {
  return fileName.replace(/\.pdf$/i, "");
}

export function clampZone(zone: SplitZone): SplitZone {
  const x = clamp(zone.x, 0, 0.99);
  const y = clamp(zone.y, 0, 0.99);
  return {
    x,
    y,
    width: clamp(zone.width, 0.01, 1 - x),
    height: clamp(zone.height, 0.01, 1 - y),
  };
}

function clamp(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.min(max, Math.max(min, value));
}

function trimNameEdges(value: string): string {
  return value.replace(/^[ ._]+|[ ._]+$/g, "");
}
