// ============================================================
// Write Oxygen review PIs into the buffer non-destructively.
//
// Because the buffer already holds every PI (it is the source of truth),
// "export" is just the buffer itself — there is no whole-document
// reserialization that could lose fidelity. Each operation below only
// touches the bytes of one annotation's PI groups.
// ============================================================

import { COLOR_RGB, type HighlightColor } from "../model/types";
import { escapeAttr } from "./attrs";
import { toOxygenTime } from "./time";
import type { AnnotationSpans } from "./parse";

// ----------------------------------------------------------------
// Thread serialization (B7)
// ----------------------------------------------------------------

export interface ReplyInput {
  author: string;
  timestamp: number;
  text: string;
  parentId: string;
  mid: number;
  resolved?: boolean;
  /** Oxygen-assigned id for replies that themselves have nested replies (enables parentID lookup). */
  id?: string;
}

export interface ThreadInput {
  root: AnnotationInput & { id: string };
  replies: ReplyInput[];
  /** When set, wraps the annotated text with oxy_custom_start/end (iff the original had one). */
  highlight?: HighlightColor;
}

/**
 * Build the opening and closing PI groups for a comment thread.
 *
 * Attribute order (matching Oxygen):
 *   root:  author, timestamp, comment, [flag,] id
 *   reply: author, timestamp, parentID, comment, mid, [flag]
 *
 * Closing order: replies in reverse mid order (each carrying mid="N"),
 * then the bare root close.
 */
export function buildThreadPiGroups(t: ThreadInput): { open: string; close: string } {
  const rootFlag = t.root.resolved ? ` flag="done"` : "";
  const openParts: string[] = [
    `<?oxy_comment_start author="${escapeAttr(t.root.author)}" ` +
    `timestamp="${toOxygenTime(t.root.timestamp)}" ` +
    `comment="${escapeAttr(t.root.text)}"${rootFlag} ` +
    `id="${escapeAttr(t.root.id)}"?>`,
  ];

  // Re-emit the highlight wrapper iff the original annotation had one (present→present, absent→absent).
  if (t.highlight) {
    openParts.push(`<?oxy_custom_start type="oxy_content_highlight" color="${COLOR_RGB[t.highlight]}"?>`);
  }

  for (const reply of t.replies) {
    const replyFlag = reply.resolved ? ` flag="done"` : "";
    const replyId = reply.id ? ` id="${escapeAttr(reply.id)}"` : "";
    openParts.push(
      `<?oxy_comment_start author="${escapeAttr(reply.author)}" ` +
      `timestamp="${toOxygenTime(reply.timestamp)}" ` +
      `parentID="${escapeAttr(reply.parentId)}" ` +
      `comment="${escapeAttr(reply.text)}" ` +
      `mid="${reply.mid}"${replyFlag}${replyId}?>`,
    );
  }

  // Close order: deeper nodes first; within same depth, higher mid first.
  // This matches Oxygen's observed behaviour for nested reply trees.
  const byId = new Map<string, ReplyInput>();
  for (const r of t.replies) {
    if (r.id) byId.set(r.id, r);
  }
  function replyDepth(r: ReplyInput): number {
    if (r.parentId === t.root.id) return 1;
    const parent = byId.get(r.parentId);
    return parent ? 1 + replyDepth(parent) : 1;
  }
  const sortedForClose = [...t.replies].sort((a, b) => {
    const dA = replyDepth(a), dB = replyDepth(b);
    if (dA !== dB) return dB - dA; // deeper closes first
    return b.mid - a.mid;          // higher mid closes first within same depth
  });
  const closeParts: string[] = sortedForClose.map((r) => `<?oxy_comment_end mid="${r.mid}"?>`);
  // Highlight wrapper (chunk 15): closes after the reply ends, before the bare root close.
  if (t.highlight) {
    closeParts.push(`<?oxy_custom_end?>`);
  }
  closeParts.push(`<?oxy_comment_end?>`);

  return { open: openParts.join(""), close: closeParts.join("") };
}

export interface AnnotationInput {
  author: string;
  timestamp: number;
  text: string;
  color: HighlightColor;
  resolved: boolean;
  /** Emit a comment PI even when text is empty (an explicit, not-yet-typed comment). */
  forceComment?: boolean;
}

/** Build the opening and closing PI groups for an annotation. */
export function buildPiGroups(a: AnnotationInput): { open: string; close: string } {
  const rgb = COLOR_RGB[a.color];
  const hlOpen = `<?oxy_custom_start type="oxy_content_highlight" color="${rgb}"?>`;
  const hlClose = `<?oxy_custom_end?>`;
  if (a.text.trim().length > 0 || a.forceComment) {
    const flag = a.resolved ? ` flag="done"` : "";
    const cOpen =
      `<?oxy_comment_start author="${escapeAttr(a.author)}" ` +
      `timestamp="${toOxygenTime(a.timestamp)}" ` +
      `comment="${escapeAttr(a.text)}"${flag}?>`;
    return { open: cOpen + hlOpen, close: hlClose + `<?oxy_comment_end?>` };
  }
  return { open: hlOpen, close: hlClose };
}

/** Insert a new annotation around the buffer text range [start, end). */
export function createAnnotation(
  buffer: string,
  start: number,
  end: number,
  a: AnnotationInput
): string {
  const { open, close } = buildPiGroups(a);
  return buffer.slice(0, start) + open + buffer.slice(start, end) + close + buffer.slice(end);
}

/** Remove an annotation's PI groups, keeping the inner text intact. */
export function deleteAnnotation(buffer: string, spans: AnnotationSpans): string {
  return (
    buffer.slice(0, spans.openStart) +
    buffer.slice(spans.contentStart, spans.contentEnd) +
    buffer.slice(spans.closeEnd)
  );
}

/** Rewrite an annotation's PI groups (text/color/resolved) in place. */
export function updateAnnotation(
  buffer: string,
  spans: AnnotationSpans,
  a: AnnotationInput
): string {
  const { open, close } = buildPiGroups(a);
  const inner = buffer.slice(spans.contentStart, spans.contentEnd);
  return buffer.slice(0, spans.openStart) + open + inner + close + buffer.slice(spans.closeEnd);
}
