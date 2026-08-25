// ============================================================
// Core domain types. Pure TypeScript — no UI or platform deps.
// The original XML buffer is the single source of truth; every
// other structure here is a projection derived from it.
// ============================================================

/** Highlight colors offered to the SME, mapped to Oxygen RGB on serialize. */
export type HighlightColor = "yellow" | "green" | "pink" | "blue";

export const COLOR_RGB: Record<HighlightColor, string> = {
  yellow: "255,243,163",
  green: "189,245,200",
  pink: "255,201,222",
  blue: "188,220,255",
};

/** Reverse lookup used when importing Oxygen highlights back into the UI. */
export function rgbToColor(rgb: string): HighlightColor {
  const norm = rgb.replace(/\s+/g, "");
  for (const [name, value] of Object.entries(COLOR_RGB)) {
    if (value === norm) return name as HighlightColor;
  }
  return "yellow";
}

/** Kind of node in the lightweight positional tree produced by the parser. */
export type NodeKind =
  | "element"
  | "text"
  | "pi"
  | "comment"
  | "doctype"
  | "cdata"
  | "document";

/**
 * A node carrying exact byte offsets into the original buffer.
 * `start`/`end` delimit the full source span of the node (including tags).
 * For elements, `innerStart`/`innerEnd` delimit the content between tags.
 */
export interface PosNode {
  kind: NodeKind;
  /** Generic identifier (element name) or PI target. */
  name?: string;
  attrs?: Record<string, string>;
  /** Raw @class attribute if present (DITA specialization ancestry). */
  classAttr?: string;
  /** Resolved DITA base type, e.g. "topic/p". Null when unknown. */
  baseType?: string | null;
  start: number;
  end: number;
  innerStart?: number;
  innerEnd?: number;
  children?: PosNode[];
  /** Verbatim text for text/comment/cdata/pi nodes. */
  value?: string;
  parent?: PosNode;
}

/**
 * Where an annotation lives in the document. Anchored by a path of child
 * indices to the containing element plus a text offset range *within that
 * element's text content* (matching how Oxygen anchors inline comments).
 */
export interface AnnotationRange {
  /** Indices from the document root down to the containing element. */
  nodePath: number[];
  /** Text offset (in the element's concatenated text) where the span starts. */
  startOffset: number;
  endOffset: number;
  /** The annotated text, used for re-anchoring and display. */
  quote: string;
}

/** A review comment / highlight — projection of inline oxy_* PIs. */
export interface Comment {
  id: string;
  author: string;
  /** Epoch millis. Formatted to Oxygen style on serialize. */
  timestamp: number;
  /** Empty string ⇒ a pure highlight with no comment text. */
  text: string;
  color: HighlightColor;
  /** true ⇒ flag="done" in Oxygen. */
  resolved: boolean;
  /** Set on replies; references the Oxygen id of the parent (parentID attribute). */
  parentId?: string;
  anchor: AnnotationRange;
  /** Threaded replies — recursive; each may itself have replies (nested threads). */
  replies?: Comment[];
  /** Oxygen mid attribute value; preserved from the source for round-trip serialization. */
  mid?: number;
}

/** Top-level application document state. */
export interface DocumentModel {
  /** File URI/path, or null for an unsaved/in-memory doc. */
  uri: string | null;
  fileName: string;
  /** The XML source — source of truth. */
  buffer: string;
  /** Read-only positional projection of `buffer`. */
  tree: PosNode;
  /** Projection of the oxy_* review PIs found in `buffer`. */
  comments: Comment[];
  dirty: boolean;
}
