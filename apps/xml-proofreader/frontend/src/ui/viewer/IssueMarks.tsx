// Ephemeral issue overlay (D5). Highlights the text each anchored Issue refers
// to, in the rendered document, WITHOUT splicing the buffer or mutating the DOM
// tree. Uses the CSS Custom Highlight API: we register Range objects under named
// highlights painted by `::highlight(...)` rules in theme.css. Degrades to a
// no-op where the API is missing (e.g. jsdom, very old webviews).
//
// An issue anchored by locateQuote (Chunk 20) lies entirely within a single
// rendered run (the matcher rejects ranges crossing tags/PIs), so each anchor
// maps onto exactly one [data-src-start] span — the same source-offset invariant
// the selection→buffer mapping already relies on.
import { useEffect } from "react";
import type { RefObject } from "react";
import { useStore } from "../store";
import type { Issue } from "../../core/issues/types";

export interface RunSpan {
  /** Source offset of the run's first character (data-src-start). */
  srcStart: number;
  /** Length of the run's text (== source span length, per the render invariant). */
  length: number;
}

export interface MarkSpec {
  issueId: string;
  /** Index into the runs array of the run containing the anchor. */
  runIndex: number;
  /** Character offsets within that run's text. */
  start: number;
  end: number;
  active: boolean;
}

/**
 * Maps anchored issues onto rendered runs. Pure (no DOM) so it is unit-testable.
 * Issues without an anchor, with an empty range, or whose range is not fully
 * contained in a single run are skipped (they still appear in the Issues list).
 */
export function computeMarks(runs: RunSpan[], issues: Issue[], activeIssueId: string | null): MarkSpec[] {
  const specs: MarkSpec[] = [];
  for (const issue of issues) {
    const a = issue.anchor;
    if (!a || a.endOffset <= a.startOffset) continue;
    const runIndex = runs.findIndex(
      (r) => a.startOffset >= r.srcStart && a.endOffset <= r.srcStart + r.length
    );
    if (runIndex === -1) continue;
    specs.push({
      issueId: issue.id,
      runIndex,
      start: a.startOffset - runs[runIndex].srcStart,
      end: a.endOffset - runs[runIndex].srcStart,
      active: issue.id === activeIssueId,
    });
  }
  return specs;
}

const HL_ALL = "issue-mark";
const HL_ACTIVE = "issue-mark-active";

interface HighlightRegistryLike {
  set(name: string, h: object): void;
  delete(name: string): void;
}
type HighlightCtor = new (...ranges: Range[]) => object;

function highlightApi(): { registry: HighlightRegistryLike; Ctor: HighlightCtor } | null {
  const w = window as unknown as { Highlight?: HighlightCtor; CSS?: { highlights?: HighlightRegistryLike } };
  if (typeof w.Highlight !== "function" || !w.CSS?.highlights) return null;
  return { registry: w.CSS.highlights, Ctor: w.Highlight };
}

/**
 * Side-effect component (renders nothing). Mount it inside the viewer; it keeps
 * the issue highlights in sync with `issues` / `activeIssueId`.
 */
export function IssueMarks({ containerRef }: { containerRef: RefObject<HTMLElement | null> }) {
  const issues = useStore((s) => s.issues);
  const activeIssueId = useStore((s) => s.activeIssueId);
  const viewMode = useStore((s) => s.viewMode);
  const rendered = useStore((s) => s.rendered);
  const zoom = useStore((s) => s.zoom);

  useEffect(() => {
    const api = highlightApi();
    if (!api) return;
    const { registry, Ctor } = api;
    const clear = () => { registry.delete(HL_ALL); registry.delete(HL_ACTIVE); };

    const root = containerRef.current;
    if (!root || viewMode !== "doc" || issues.length === 0) { clear(); return clear; }

    // Collect rendered runs in document order with their text nodes.
    const spans = Array.from(root.querySelectorAll<HTMLElement>("[data-src-start]"));
    const runs: RunSpan[] = [];
    const nodes: (Text | null)[] = [];
    for (const span of spans) {
      const first = span.firstChild;
      const textNode = first && first.nodeType === Node.TEXT_NODE ? (first as Text) : null;
      runs.push({ srcStart: Number(span.dataset.srcStart), length: textNode?.nodeValue?.length ?? 0 });
      nodes.push(textNode);
    }

    const all: Range[] = [];
    const active: Range[] = [];
    for (const spec of computeMarks(runs, issues, activeIssueId)) {
      const node = nodes[spec.runIndex];
      const len = node?.nodeValue?.length ?? 0;
      if (!node || spec.start < 0 || spec.end > len || spec.start >= spec.end) continue;
      const range = document.createRange();
      range.setStart(node, spec.start);
      range.setEnd(node, spec.end);
      (spec.active ? active : all).push(range);
    }

    if (all.length) registry.set(HL_ALL, new Ctor(...all)); else registry.delete(HL_ALL);
    if (active.length) registry.set(HL_ACTIVE, new Ctor(...active)); else registry.delete(HL_ACTIVE);

    return clear;
  }, [containerRef, issues, activeIssueId, viewMode, rendered, zoom]);

  return null;
}
