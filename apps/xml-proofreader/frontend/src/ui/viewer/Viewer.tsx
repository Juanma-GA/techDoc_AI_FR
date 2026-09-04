// Central WYSIWYG viewer: renders the PDF-like page, handles text selection →
// floating toolbar → annotation, plus the XML source view, zoom and scroll.
import { useEffect, useMemo, useRef, useState } from "react";
import { useStore, type SelectionRange } from "../store";
import { useSession } from "../sessionStore";
import { Blocks, type RenderCtx } from "./Blocks";
import { InlineRuns } from "./InlineRuns";
import { IssueMarks } from "./IssueMarks";
import { XmlView } from "../xmlview/XmlView";
import { LinkResolver } from "../../core/map/links";
import type { HighlightColor } from "../../core/model/types";

const SWATCHES: HighlightColor[] = ["yellow", "green", "pink", "blue"];
const SWATCH_VAR: Record<HighlightColor, string> = {
  yellow: "var(--hl-yellow)", green: "var(--hl-green)", pink: "var(--hl-pink)", blue: "var(--hl-blue)",
};

interface FloatPos { left: number; top: number; }

function IconDocument() {
  return (
    <svg viewBox="0 0 24 24" width="54" height="54" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7z" />
      <path d="M14 2v5h5" />
      <path d="M9 13h6M9 17h6" />
    </svg>
  );
}

function IconUnsupported() {
  return (
    <svg viewBox="0 0 24 24" width="54" height="54" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
  );
}

export function Viewer() {
  const rendered = useStore((s) => s.rendered);
  const comments = useStore((s) => s.comments);
  const activeId = useStore((s) => s.activeId);
  const viewMode = useStore((s) => s.viewMode);
  const zoom = useStore((s) => s.zoom);
  const addAnnotation = useStore((s) => s.addAnnotation);
  const focusByKey = useStore((s) => s.focusByKey);
  const hasDoc = useStore((s) => s.buffer.length > 0);
  const fileName = useStore((s) => s.fileName);
  const openFile = useStore((s) => s.openFile);
  const languageError = useStore((s) => s.languageError);
  const isMap = useStore((s) => s.mapModel !== null);
  const keydefs = useStore((s) => s.mapModel?.keydefs);

  const wrapRef = useRef<HTMLDivElement>(null);
  const [pending, setPending] = useState<SelectionRange | null>(null);
  const [floatPos, setFloatPos] = useState<FloatPos | null>(null);

  const activeIssueId = useStore((s) => s.activeIssueId);
  const issues = useStore((s) => s.issues);
  const defaultHighlight = useSession((s) => s.settings.prefs.defaultHighlight);

  const commentsByKey = useMemo(() => {
    const m = new Map<number, (typeof comments)[number]>();
    for (const c of comments) m.set(c.key, c);
    return m;
  }, [comments]);

  const activeKey = useMemo(
    () => comments.find((c) => c.id === activeId)?.key ?? null,
    [comments, activeId]
  );

  function onXrefClick(href: string, keyref?: string) {
    // Resolve through the core LinkResolver (keydefs come from the open map, if
    // any). Only same-document targets scroll here; external file links resolve
    // to {external} and are intentionally not navigated in the viewer.
    const resolver = new LinkResolver(keydefs ?? {}, async () => null);
    const res = keyref && !href ? resolver.resolveKeyref(keyref) : resolver.resolveHref(href, keyref);
    if (res.kind !== "internal") return;
    const target = wrapRef.current?.querySelector(`#${CSS.escape(res.targetId)}`)
      ?? document.getElementById(res.targetId);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  const ctx: RenderCtx = { commentsByKey, activeKey, onFocus: focusByKey, onXrefClick, defaultHighlight };

  // Scroll the active highlight into view when selected from the panel.
  useEffect(() => {
    if (activeKey == null || viewMode !== "doc") return;
    const el = wrapRef.current?.querySelector(`[data-comment-key="${activeKey}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [activeKey, viewMode]);

  // Scroll to the anchor of the active issue (F5, ADR-0028).
  useEffect(() => {
    if (!activeIssueId || viewMode !== "doc") return;
    const issue = issues.find((x) => x.id === activeIssueId);
    if (!issue) return;
    const scrollArea = wrapRef.current;
    if (!scrollArea) return;

    // 1. Prefer offset-based scroll: find the span whose data-src-start is the
    //    largest value still ≤ the anchor start (closest enclosing run).
    if (issue.anchor) {
      const target = findSpanByOffset(scrollArea, issue.anchor.startOffset);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
    }

    // 2. Fall back to normalised-needle walk (spaces + case collapsed).
    if (!issue.quote) return;
    const needle = issue.quote.slice(0, 40).replace(/\s+/g, " ").trim().toLowerCase();
    const walker = document.createTreeWalker(scrollArea, NodeFilter.SHOW_TEXT);
    let node: Text | null;
    while ((node = walker.nextNode() as Text | null)) {
      const text = (node.nodeValue ?? "").replace(/\s+/g, " ").toLowerCase();
      if (text.includes(needle)) {
        node.parentElement?.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
    }
    // 3. Not localizable — toast so the user knows the scroll failed.
    if (issue.quote) {
      useStore.getState().toast("No se pudo localizar la cita en el documento", "⚠");
    }
  }, [activeIssueId, issues, viewMode]);

  function onMouseUp() {
    if (viewMode !== "doc" || isMap) return; // map/merged views are read-only
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.toString().trim()) {
      setPending(null); setFloatPos(null); return;
    }
    const range = sel.getRangeAt(0);
    const start = sourceOffset(range.startContainer, range.startOffset);
    const end = sourceOffset(range.endContainer, range.endOffset);
    if (start == null || end == null || end <= start) { setPending(null); setFloatPos(null); return; }
    const rect = range.getBoundingClientRect();
    const wrapRect = wrapRef.current!.getBoundingClientRect();
    setPending({ start: Math.min(start, end), end: Math.max(start, end), quote: sel.toString() });
    setFloatPos({
      left: Math.max(8, rect.left + rect.width / 2 - wrapRect.left - 90),
      top: rect.top - wrapRect.top - 46,
    });
  }

  function apply(color: HighlightColor, withComment: boolean) {
    if (!pending) return;
    addAnnotation(pending, color, withComment);
    window.getSelection()?.removeAllRanges();
    setPending(null); setFloatPos(null);
  }

  return (
    <div className="viewer-wrap" ref={wrapRef} onMouseDown={(e) => {
      if (!(e.target as HTMLElement).closest(".float-tb")) { setFloatPos(null); }
    }}>
      <Toolbar hasDoc={hasDoc} isMap={isMap} />
      <IssueMarks containerRef={wrapRef} />
      <div className="scroll-area" onMouseUp={onMouseUp}>
        {!hasDoc ? (
          <div className="empty-doc">
            <div className="big" aria-hidden="true"><IconDocument /></div>
            <h2>No document open</h2>
            <p>Open a DITA / S1000D file to start reviewing. You annotate a working copy; use
              <b> Export / Save as…</b> to write it to a file, then <b>Save</b> to update that file.</p>
            <button className="btn primary" onClick={openFile}>Open XML…</button>
          </div>
        ) : languageError ? (
          <div className="lang-error">
            <div className="big" aria-hidden="true"><IconUnsupported /></div>
            <h2>Unsupported document language</h2>
            <p>The loaded file was detected as <b>{languageError.name}</b>.</p>
            <p className="muted">XML Proofreader supports <b>DITA 1.3</b> and <b>S1000D</b> issues
              <b> 3.0, 4.0, 4.1, 4.2</b>. <code>{languageError.name}</code> is not supported.</p>
          </div>
        ) : viewMode === "doc" ? (
          <article className="page doc" style={{ zoom: zoom / 100 } as React.CSSProperties}>
            <div className="page-header"><span>Confidential — Review working copy</span></div>
            {rendered.title && <div className="doc-title"><InlineRuns inlines={rendered.title} commentsByKey={commentsByKey} activeKey={activeKey} onFocus={focusByKey} onXrefClick={onXrefClick} defaultHighlight={defaultHighlight} /></div>}
            {rendered.subtitle && <div className="doc-sub"><InlineRuns inlines={rendered.subtitle} commentsByKey={commentsByKey} activeKey={activeKey} onFocus={focusByKey} onXrefClick={onXrefClick} defaultHighlight={defaultHighlight} /></div>}
            <Blocks blocks={rendered.blocks} ctx={ctx} />
            <div className="page-footer"><span>{fileName}</span><span>Review working copy</span></div>
          </article>
        ) : (
          <div className="xmlview" style={{ zoom: zoom / 100 } as React.CSSProperties}>
            <XmlView />
          </div>
        )}
      </div>

      {floatPos && pending && (
        <div className="float-tb" style={{ left: floatPos.left, top: floatPos.top }}>
          {SWATCHES.map((c) => (
            <div key={c} className="swatch" title={c} style={{ background: SWATCH_VAR[c] }} onClick={() => apply(c, false)} />
          ))}
          <div className="sep" />
          <button onClick={() => apply(defaultHighlight, true)}>Comment</button>
        </div>
      )}
    </div>
  );
}

function Toolbar({ hasDoc, isMap }: { hasDoc: boolean; isMap: boolean }) {
  const viewMode = useStore((s) => s.viewMode);
  const setView = useStore((s) => s.setView);
  const setZoom = useStore((s) => s.setZoom);
  const zoom = useStore((s) => s.zoom);
  const merged = useStore((s) => s.merged);
  const resolveAllTopics = useStore((s) => s.resolveAllTopics);
  const collapseMap = useStore((s) => s.collapseMap);
  return (
    <div className="viewer-toolbar">
      {hasDoc && (
        <div className="seg">
          <button className={viewMode === "doc" ? "active" : ""} onClick={() => setView("doc")}>Document</button>
          <button className={viewMode === "xml" ? "active" : ""} onClick={() => setView("xml")}>XML</button>
        </div>
      )}
      {isMap && (
        <button className={`mini-btn${merged ? " on" : ""}`} style={{ marginLeft: 6 }}
          onClick={() => (merged ? collapseMap() : resolveAllTopics())}>
          {merged ? "Map navigation" : "Resolve all topics"}
        </button>
      )}
      {hasDoc && !isMap && (
        <span className="chip" style={{ marginLeft: 10 }}>
          <span className="dot" style={{ background: "var(--comment)" }} /> Select text to highlight or comment
        </span>
      )}
      <div className="vt-spacer" />
      {hasDoc && (
        <div className="zoom">
          <button onClick={() => setZoom(-1)}>−</button>
          <span>{zoom}%</span>
          <button onClick={() => setZoom(1)}>+</button>
        </div>
      )}
    </div>
  );
}

/**
 * Find the element with the largest data-src-start that is still ≤ the target
 * buffer offset (the closest enclosing run). Used by the issue-scroll effect to
 * locate the DOM element that corresponds to an issue anchor.
 */
export function findSpanByOffset(container: Element, offset: number): Element | null {
  const spans = container.querySelectorAll("[data-src-start]");
  let best: Element | null = null;
  let bestStart = -1;
  for (const span of spans) {
    const start = Number((span as HTMLElement).dataset.srcStart);
    if (start <= offset && start > bestStart) {
      bestStart = start;
      best = span;
    }
  }
  return best;
}

/**
 * Map a DOM (node, offset) to an absolute buffer offset using the data-src-start
 * carried by each text-run span.
 */
function sourceOffset(node: Node, offset: number): number | null {
  let el: HTMLElement | null =
    node.nodeType === Node.TEXT_NODE ? (node.parentElement as HTMLElement) : (node as HTMLElement);
  // Walk up to the nearest element carrying a source offset.
  while (el && el.dataset.srcStart === undefined) el = el.parentElement;
  if (!el) return null;
  const base = Number(el.dataset.srcStart);
  if (node.nodeType === Node.TEXT_NODE) return base + offset;
  // Selection landed on an element boundary: approximate with the base.
  return base;
}
