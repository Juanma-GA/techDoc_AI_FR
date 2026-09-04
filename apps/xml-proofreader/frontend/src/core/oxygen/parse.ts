// ============================================================
// Parse Oxygen review processing instructions out of the positional tree
// into UI-facing Comment objects. Also records, per annotation, the exact
// buffer spans of its opening/closing PI groups so the serializer can
// delete or rewrite it non-destructively.
//
// Recognized structure (as written by Oxygen and by this app):
//
// Simple comment (no thread):
//   <?oxy_comment_start author=… timestamp=… comment=… [flag="done"]?>
//     <?oxy_custom_start type="oxy_content_highlight" color="r,g,b"?>
//       …annotated text…
//     <?oxy_custom_end?>
//   <?oxy_comment_end?>
//
// Thread (root + replies, all sharing the same text span):
//   <?oxy_comment_start … comment=… id="ROOT_ID"?>
//   <?oxy_comment_start … comment=… parentID="ROOT_ID" mid="1"?>
//   …
//   …annotated text…
//   …
//   <?oxy_comment_end mid="1"?>
//   <?oxy_comment_end?>   ← bare close always belongs to the root
//
// A comment-less highlight is just the oxy_custom_start/end pair.
// ============================================================

import type { Comment, HighlightColor, PosNode } from "../model/types";
import { rgbToColor } from "../model/types";
import { walk, pathOf } from "../xml/tree";
import { parsePiAttrs } from "./attrs";
import { fromOxygenTime } from "./time";

export interface AnnotationSpans {
  /** Start of the opening PI group in the buffer. */
  openStart: number;
  /** Start of the inner annotated text (end of the opening PI group). */
  contentStart: number;
  /** End of the inner annotated text (start of the closing PI group). */
  contentEnd: number;
  /** End of the closing PI group. */
  closeEnd: number;
}

export interface ParsedComment extends Comment {
  /** Unifying key = source offset of the opening PI. Matches run.commentKey. */
  key: number;
  spans: AnnotationSpans;
  /** True when the root had an oxy_custom_start highlight wrapper (used by serializer to re-emit it iff present). */
  hasHighlight?: boolean;
}

function colorOf(customPi: PosNode | undefined): HighlightColor {
  const m = customPi?.value?.match(/color="([^"]+)"/);
  return m ? rgbToColor(m[1]) : "yellow";
}

function quoteOf(buffer: string, from: number, to: number): string {
  return buffer
    .slice(from, to)
    .replace(/<\?[\s\S]*?\?>/g, "") // strip any inner PIs
    .replace(/<[^>]*>/g, "") // strip inline element tags
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(+d))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&");
}

type OpenEntry = {
  pi: PosNode;
  customPi?: PosNode;
  contentStart: number;
  mid?: string;
  parentId?: string;
};

function emitThread(
  stack: OpenEntry[],
  closingCustom: PosNode | null,
  rootClose: PosNode,
  firstCloseStart: number | null,
  el: PosNode,
  buffer: string,
  out: ParsedComment[]
): void {
  const rootEntry = stack[0];
  const replyEntries = stack.slice(1);

  const rootAttrs = parsePiAttrs(rootEntry.pi.value ?? "");
  const contentStart = stack[stack.length - 1].contentStart;
  const contentEnd = closingCustom
    ? closingCustom.start
    : (firstCloseStart ?? rootClose.start);
  const quote = quoteOf(buffer, contentStart, contentEnd);

  // Build tree: create all reply nodes, then attach each to its Oxygen parent.
  type ReplyNode = Comment & { _oxyId?: string };
  const byOxyId = new Map<string, ReplyNode>();
  const replyNodes: ReplyNode[] = replyEntries.map((entry) => {
    const a = parsePiAttrs(entry.pi.value ?? "");
    const oxyId = a.id; // may be undefined (most replies have no id unless they have children)
    const mid = a.mid ? parseInt(a.mid, 10) : undefined;
    const node: ReplyNode = {
      id: oxyId ?? `c:${a.timestamp ?? ""}:${a.author ?? ""}:${a.mid ?? ""}`,
      author: a.author ?? "Unknown",
      timestamp: a.timestamp ? fromOxygenTime(a.timestamp) : Date.now(),
      text: a.comment ?? "",
      color: "yellow" as HighlightColor,
      resolved: a.flag === "done",
      parentId: a.parentID,
      anchor: { nodePath: pathOf(el), startOffset: 0, endOffset: 0, quote },
      replies: [],
      mid,
      _oxyId: oxyId,
    };
    if (oxyId) byOxyId.set(oxyId, node);
    return node;
  });

  // Attach each reply to its parent (root or another reply).
  const rootOxyId = rootAttrs.id;
  const replies: Comment[] = [];
  for (const node of replyNodes) {
    const parentOxyId = node.parentId;
    if (!parentOxyId || parentOxyId === rootOxyId) {
      replies.push(node);
    } else {
      const parent = byOxyId.get(parentOxyId);
      if (parent) {
        parent.replies = parent.replies ?? [];
        parent.replies.push(node);
      } else {
        replies.push(node); // fallback: attach to root
      }
    }
  }

  out.push({
    id: rootAttrs.id ?? `c:${rootAttrs.timestamp ?? ""}:${rootAttrs.author ?? ""}`,
    author: rootAttrs.author ?? "Unknown",
    timestamp: rootAttrs.timestamp ? fromOxygenTime(rootAttrs.timestamp) : Date.now(),
    text: rootAttrs.comment ?? "",
    color: colorOf(rootEntry.customPi),
    resolved: rootAttrs.flag === "done",
    anchor: { nodePath: pathOf(el), startOffset: 0, endOffset: 0, quote },
    replies,
    hasHighlight: !!rootEntry.customPi,
    key: rootEntry.pi.start,
    spans: {
      openStart: rootEntry.pi.start,
      contentStart,
      contentEnd,
      closeEnd: rootClose.end,
    },
  });
}

function emitHighlight(
  open: { pi: PosNode; contentStart: number },
  endPi: PosNode,
  el: PosNode,
  buffer: string,
  out: ParsedComment[]
): void {
  const quote = quoteOf(buffer, open.contentStart, endPi.start);
  out.push({
    id: `h:${colorOf(open.pi)}:${quote.slice(0, 24)}`,
    author: "",
    timestamp: Date.now(),
    text: "",
    color: colorOf(open.pi),
    resolved: false,
    anchor: { nodePath: pathOf(el), startOffset: 0, endOffset: 0, quote },
    key: open.pi.start,
    spans: {
      openStart: open.pi.start,
      contentStart: open.contentStart,
      contentEnd: endPi.start,
      closeEnd: endPi.end,
    },
  });
}

function scanElement(el: PosNode, buffer: string, out: ParsedComment[]): void {
  const openStack: OpenEntry[] = [];
  let firstCloseStart: number | null = null;
  let closingCustom: PosNode | null = null;
  let openCustom: { pi: PosNode; contentStart: number } | null = null;

  for (const k of el.children ?? []) {
    if (k.kind !== "pi") continue;
    switch (k.name) {
      case "oxy_comment_start": {
        const a = parsePiAttrs(k.value ?? "");
        openStack.push({
          pi: k,
          contentStart: k.end,
          mid: a.mid,
          parentId: a.parentID,
        });
        firstCloseStart = null;
        closingCustom = null;
        break;
      }
      case "oxy_custom_start":
        if (openStack.length > 0 && !openStack[openStack.length - 1].customPi) {
          openStack[openStack.length - 1].customPi = k;
          openStack[openStack.length - 1].contentStart = k.end;
        } else {
          openCustom = { pi: k, contentStart: k.end };
        }
        break;
      case "oxy_custom_end":
        if (openCustom) {
          emitHighlight(openCustom, k, el, buffer, out);
          openCustom = null;
        } else if (openStack.length > 0 && openStack[openStack.length - 1].customPi) {
          closingCustom = k;
        }
        break;
      case "oxy_comment_end": {
        if (openStack.length === 0) break;
        if (firstCloseStart === null) firstCloseStart = k.start;
        const a = parsePiAttrs(k.value ?? "");
        if (!a.mid) {
          // Bare close → root's close → emit the complete thread (or single comment)
          emitThread(openStack, closingCustom, k, firstCloseStart, el, buffer, out);
          openStack.length = 0;
          firstCloseStart = null;
          closingCustom = null;
        }
        // Reply closes (a.mid is set) are consumed to advance firstCloseStart tracking
        break;
      }
    }
  }
}

/** Extract all review annotations from a parsed document, in document order. */
export function parseComments(tree: PosNode, buffer: string): ParsedComment[] {
  const out: ParsedComment[] = [];
  walk(tree, (n) => {
    if (n.kind === "element") scanElement(n, buffer, out);
  });
  out.sort((a, b) => a.key - b.key);
  return out;
}
