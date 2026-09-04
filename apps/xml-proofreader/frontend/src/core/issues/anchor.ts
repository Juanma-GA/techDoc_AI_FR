import type { AnnotationRange } from "../model/types";

/** Result of locating a quote in the source buffer. */
export interface QuoteMatch {
  /** Source offset where the matched span starts. */
  startOffset: number;
  /** Source offset just past the matched span. */
  endOffset: number;
  /** The exact source substring that was matched (use this for splicing). */
  quote: string;
  /**
   * Whitespace-normalized needle (single spaces, trimmed). Use this to find the
   * span in *rendered* text (the DOM overlay), where whitespace is collapsed.
   */
  needle: string;
}

export interface LocateOptions {
  /** Start searching at this source offset (default 0). */
  from?: number;
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** True when the substring contains an XML tag delimiter (so it crosses markup). */
function crossesTag(s: string): boolean {
  return s.includes("<") || s.includes(">");
}

/**
 * True when `offset` falls inside an open XML tag (e.g. inside `<element ...>`).
 * Used to reject partial-locate matches that land on a tag name rather than text content.
 */
export function isInsideTag(buffer: string, offset: number): boolean {
  const lastOpen = buffer.lastIndexOf("<", offset - 1);
  if (lastOpen === -1) return false;
  const close = buffer.indexOf(">", lastOpen);
  return close === -1 || close >= offset;
}

/**
 * Normalize a quote for buffer-search purposes (G-Q3, ADR-0032).
 * Encodes `&` → `&amp;` so AI-decoded text (`&`) matches buffer entities (`&amp;`).
 * Normalizes typographic quotes and dashes to ASCII equivalents.
 * Does NOT encode `<`/`>` — those trigger crossesTag rejection earlier.
 */
function normalizeForSearch(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/[‘’ʼ]/g, "'")   // typographic single quotes / apostrophe
    .replace(/[“”]/g, '"')          // typographic double quotes
    .replace(/[–—−]/g, "-");   // en-dash, em-dash, minus sign
}

/**
 * Locates `quote` in `buffer` with whitespace-normalized matching, returning a
 * source range when possible.
 *
 * Contract:
 *  - Whitespace runs (spaces, tabs, newlines) are tolerated: a quote of visible
 *    prose matches even when the source wraps/indents it differently.
 *  - Quotes that cross element boundaries are **rejected** (returns undefined):
 *    the `\s+` joins between tokens never match `<...>`, and any matched span that
 *    still contains a tag delimiter is discarded. This keeps a later splice safe
 *    (it stays inside a single text run, never inside or across tags).
 *  - Matching tiers (most precise first): exact (whitespace-identical) →
 *    whitespace-normalized, case-sensitive → whitespace-normalized,
 *    case-insensitive. The case-insensitive tier (E2/ADR-0021) is a last resort
 *    so a quote that differs only in capitalization still anchors; the earlier
 *    tiers always win when they match.
 *  - First occurrence wins (matches the historical anchorByQuote behaviour).
 *
 * Returns undefined when the quote is empty or cannot be located as contiguous
 * visible text.
 */
export function locateQuote(
  buffer: string,
  quote: string,
  opts?: LocateOptions
): QuoteMatch | undefined {
  const needle = quote.replace(/\s+/g, " ").trim();
  if (!needle) return undefined;
  const from = Math.max(0, opts?.from ?? 0);

  // Fast path: exact, whitespace-identical occurrence.
  const exactIdx = buffer.indexOf(quote, from);
  if (exactIdx !== -1 && !crossesTag(quote)) {
    return { startOffset: exactIdx, endOffset: exactIdx + quote.length, quote, needle };
  }

  // Normalized path: collapse inter-token whitespace to \s+ so source wrapping
  // and indentation are tolerated, but tags between tokens are not. Try a
  // case-sensitive match first and, only if that finds nothing, a
  // case-insensitive one (E2/ADR-0021). Tag-crossing rejection and "first
  // occurrence wins" hold in both tiers; the returned range is always the real
  // source substring.
  const tokens = needle.split(" ").map(escapeRegExp);
  if (tokens.some((t) => t.length === 0)) return undefined;
  const pattern = tokens.join("\\s+");
  const haystack = from > 0 ? buffer.slice(from) : buffer;

  for (const flags of ["", "i"]) {
    const m = new RegExp(pattern, flags).exec(haystack);
    if (!m) continue;
    const start = (from > 0 ? from : 0) + m.index;
    const matched = m[0];
    if (crossesTag(matched)) return undefined;
    return { startOffset: start, endOffset: start + matched.length, quote: matched, needle };
  }

  // Tier 4 — entity + typographic normalization (G-Q3, ADR-0032):
  // the AI quote may carry decoded `&` where the buffer stores `&amp;`, or
  // typographic quotes/dashes where the source uses ASCII. Normalize the needle
  // and retry with the same whitespace-collapsed, case-tolerant matching.
  const normalizedNeedle = normalizeForSearch(needle);
  if (normalizedNeedle !== needle) {
    const normTokens = normalizedNeedle.split(" ").map(escapeRegExp);
    if (normTokens.every((t) => t.length > 0)) {
      const normPattern = normTokens.join("\\s+");
      for (const flags of ["", "i"]) {
        const m = new RegExp(normPattern, flags).exec(haystack);
        if (!m) continue;
        const start = (from > 0 ? from : 0) + m.index;
        const matched = m[0];
        if (crossesTag(matched) || isInsideTag(buffer, start)) continue;
        return { startOffset: start, endOffset: start + matched.length, quote: matched, needle: normalizedNeedle };
      }
    }
  }

  return undefined;
}

/**
 * Locates the longest safe *prefix* of `quote`'s tokens that fits inside a
 * single text run (no tag-crossing, not inside a tag).  Returns undefined when
 * the quote has only one token (nothing to shorten) or no prefix matches.
 *
 * Used as the second-level fallback in `acceptSuggestion` (G2, ADR-0032):
 * when the full quote crosses element boundaries, anchor over the part that is
 * safely reachable.
 */
export function locateQuotePartial(
  buffer: string,
  quote: string,
  opts?: LocateOptions
): QuoteMatch | undefined {
  const needle = quote.replace(/\s+/g, " ").trim();
  if (!needle) return undefined;
  const rawTokens = needle.split(" ");
  if (rawTokens.length < 2) return undefined; // single-token — already tried by locateQuote
  const from = Math.max(0, opts?.from ?? 0);
  const haystack = from > 0 ? buffer.slice(from) : buffer;
  const escapedTokens = rawTokens.map(escapeRegExp);

  // Try prefixes from "all-but-last" down to "first token only".
  for (let len = escapedTokens.length - 1; len >= 1; len--) {
    const pattern = escapedTokens.slice(0, len).join("\\s+");
    for (const flags of ["", "i"]) {
      const m = new RegExp(pattern, flags).exec(haystack);
      if (!m) continue;
      const start = (from > 0 ? from : 0) + m.index;
      const matched = m[0];
      if (crossesTag(matched) || isInsideTag(buffer, start)) continue;
      return {
        startOffset: start,
        endOffset: start + matched.length,
        quote: matched,
        needle: rawTokens.slice(0, len).join(" "),
      };
    }
  }
  return undefined;
}

/**
 * Backwards-compatible wrapper: returns an AnnotationRange anchored by quote.
 * Now backed by the normalized {@link locateQuote}.
 */
export function anchorByQuote(buffer: string, quote: string): AnnotationRange | undefined {
  const m = locateQuote(buffer, quote);
  if (!m) return undefined;
  return { nodePath: [], startOffset: m.startOffset, endOffset: m.endOffset, quote: m.quote };
}
