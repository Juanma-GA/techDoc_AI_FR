// Renders inline text runs. Every run is a <span> tagged with its exact
// source offset (data-src-start) so a DOM selection maps back to the buffer.
// Runs inside an oxy highlight get the highlight classes and are clickable.
// LinkRun (xref/internalRef) renders as a styled link span.
import type { Inline } from "../../core/render/model";
import type { HighlightColor } from "../../core/model/types";
import type { ParsedComment } from "../../core/oxygen/parse";

interface Props {
  inlines: Inline[];
  commentsByKey: Map<number, ParsedComment>;
  activeKey: number | null;
  onFocus: (key: number) => void;
  onXrefClick?: (href: string, keyref?: string) => void;
  /** Fallback color for comment runs that have no oxy_custom_start highlight (visual only). */
  defaultHighlight?: HighlightColor;
}

export function InlineRuns({ inlines, commentsByKey, activeKey, onFocus, onXrefClick, defaultHighlight }: Props) {
  return (
    <>
      {inlines.map((run, i) => {
        if (run.kind === "link") {
          // G1: resolved comments render as plain text (no color, no focus click).
          const resolved = run.commentKey !== undefined && commentsByKey.get(run.commentKey)?.resolved;
          const hlCls = run.color && !resolved ? ` hl c-${run.color}` : "";
          return (
            <span
              key={i}
              className={`xref${hlCls}`}
              data-src-start={run.srcStart}
              data-comment-key={run.commentKey}
              title={run.href}
              onClick={(e) => {
                e.stopPropagation();
                if (run.commentKey !== undefined && !resolved) onFocus(run.commentKey);
                if (onXrefClick) onXrefClick(run.href, run.keyref);
              }}
            >
              {run.text}
            </span>
          );
        }
        // Use the run's own color, or fall back to defaultHighlight for comment runs without a wrapper.
        const effectiveColor = run.color ?? (run.commentKey !== undefined ? defaultHighlight : undefined);
        if (effectiveColor && run.commentKey !== undefined) {
          const c = commentsByKey.get(run.commentKey);
          // G1: resolved comments render as plain text (no highlight class, no focus click).
          if (c?.resolved) {
            return <span key={i} data-src-start={run.srcStart}>{run.text}</span>;
          }
          const hasNote = !!c && c.text.trim().length > 0;
          const active = run.commentKey === activeKey;
          const cls = `hl c-${effectiveColor}${hasNote ? " has-note" : ""}${active ? " active" : ""}`;
          return (
            <span
              key={i}
              className={cls}
              data-src-start={run.srcStart}
              data-comment-key={run.commentKey}
              onClick={() => onFocus(run.commentKey!)}
            >
              {run.text}
            </span>
          );
        }
        return (
          <span key={i} data-src-start={run.srcStart}>
            {run.text}
          </span>
        );
      })}
    </>
  );
}
