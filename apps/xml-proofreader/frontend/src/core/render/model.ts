// ============================================================
// Presentation model — a plain, UI-agnostic data structure the React
// viewer renders. Every inline run carries its source offset so a DOM
// selection can be mapped back to an exact buffer position (used in F3).
// ============================================================

import type { HighlightColor } from "../model/types";

export interface Span {
  start: number;
  end: number;
}

/** A run of text tied to its exact source offset. */
export interface TextRun {
  kind: "text";
  text: string;
  /** Offset in the buffer where this run's first character lives. */
  srcStart: number;
  /** Active highlight color, if this run sits inside an oxy highlight. */
  color?: HighlightColor;
  /** Stable key (source offset of the originating oxy_comment_start), if any. */
  commentKey?: number;
}

/** A cross-reference run (xref / internalRef) with a navigable href. */
export interface LinkRun {
  kind: "link";
  text: string;
  srcStart: number;
  /** Raw href value (e.g. "#section", "other.dita#x", "#para-001"). */
  href: string;
  /** DITA @keyref, when the reference is (also) by key. */
  keyref?: string;
  color?: HighlightColor;
  commentKey?: number;
}

export type Inline = TextRun | LinkRun;

/** A table cell that may span multiple columns/rows (CALS namest/nameend/morerows). */
export interface TableCell {
  inlines: Inline[];
  colSpan: number;
  rowSpan: number;
  header: boolean;
}
export interface TableRow {
  cells: TableCell[];
}

export interface BaseBlock {
  /** Source span of the originating element (for debugging / mapping). */
  src: Span;
  /** Stable id for outline / scroll targeting. */
  id: string;
}

export type Block =
  | (BaseBlock & { kind: "doc-title"; inlines: Inline[] })
  | (BaseBlock & { kind: "subtitle"; inlines: Inline[] })
  | (BaseBlock & { kind: "heading"; level: 2 | 3; inlines: Inline[] })
  | (BaseBlock & { kind: "para"; inlines: Inline[] })
  | (BaseBlock & { kind: "note"; noteType: string; label: string; inlines: Inline[] })
  | (BaseBlock & { kind: "list"; ordered: boolean; items: Block[][] })
  | (BaseBlock & { kind: "steps"; steps: Block[][] })
  | (BaseBlock & { kind: "table"; caption: Inline[] | null; columns: number; headRows: TableRow[]; bodyRows: TableRow[] })
  | (BaseBlock & { kind: "figure"; caption: Inline[] | null; imageHref: string | null; imageScale?: number })
  | (BaseBlock & { kind: "generic"; name: string; inlines: Inline[]; blocks: Block[] });

export interface RenderedDoc {
  title: Inline[] | null;
  subtitle: Inline[] | null;
  blocks: Block[];
  /** Headings (or map hierarchy entries) for the outline, in document order. */
  outline: { id: string; text: string; level: number; href?: string | null }[];
}
