// Recursive renderer for the presentation model → PDF-like HTML.
import type { Block, Inline } from "../../core/render/model";
import type { HighlightColor } from "../../core/model/types";
import type { ParsedComment } from "../../core/oxygen/parse";
import { InlineRuns } from "./InlineRuns";
import { useImageSrc } from "./useImageSrc";

export interface RenderCtx {
  commentsByKey: Map<number, ParsedComment>;
  activeKey: number | null;
  onFocus: (key: number) => void;
  onXrefClick?: (href: string, keyref?: string) => void;
  defaultHighlight?: HighlightColor;
}

export function Blocks({ blocks, ctx }: { blocks: Block[]; ctx: RenderCtx }) {
  return (
    <>
      {blocks.map((b, i) => (
        <BlockView key={`${b.id}-${i}`} block={b} ctx={ctx} />
      ))}
    </>
  );
}

function Inl({ inlines, ctx }: { inlines: Inline[]; ctx: RenderCtx }) {
  return <InlineRuns inlines={inlines} commentsByKey={ctx.commentsByKey} activeKey={ctx.activeKey} onFocus={ctx.onFocus} onXrefClick={ctx.onXrefClick} defaultHighlight={ctx.defaultHighlight} />;
}

function BlockView({ block: b, ctx }: { block: Block; ctx: RenderCtx }) {
  switch (b.kind) {
    case "heading":
      return (
        <h2 id={b.id} data-block={b.id}>
          <Inl inlines={b.inlines} ctx={ctx} />
        </h2>
      );
    case "para":
      return (
        <p id={b.id}>
          <Inl inlines={b.inlines} ctx={ctx} />
        </p>
      );
    case "note": {
      const icon = b.noteType === "danger" ? "⛔" : /warn|caution|attention/.test(b.noteType) ? "⚠️" : "ℹ️";
      return (
        <div className={`note ${b.noteType}`} id={b.id}>
          <span className="ni">{icon}</span>
          <div>
            <span className="nl">{b.label}</span>
            <Inl inlines={b.inlines} ctx={ctx} />
          </div>
        </div>
      );
    }
    case "list":
      return b.ordered ? (
        <ol id={b.id}>{b.items.map((it, i) => <li key={i}><Blocks blocks={it} ctx={ctx} /></li>)}</ol>
      ) : (
        <ul id={b.id}>{b.items.map((it, i) => <li key={i}><Blocks blocks={it} ctx={ctx} /></li>)}</ul>
      );
    case "steps":
      return (
        <ol className="step-list" id={b.id}>
          {b.steps.map((st, i) => (
            <li key={i}><Blocks blocks={st} ctx={ctx} /></li>
          ))}
        </ol>
      );
    case "table": {
      const cell = (c: import("../../core/render/model").TableCell, i: number) => {
        const span = { colSpan: c.colSpan > 1 ? c.colSpan : undefined, rowSpan: c.rowSpan > 1 ? c.rowSpan : undefined };
        return c.header
          ? <th key={i} {...span}><Inl inlines={c.inlines} ctx={ctx} /></th>
          : <td key={i} className={c.colSpan > 1 || c.rowSpan > 1 ? "spanc" : undefined} {...span}><Inl inlines={c.inlines} ctx={ctx} /></td>;
      };
      return (
        <table className="dtab" id={b.id}>
          {b.caption && <caption><Inl inlines={b.caption} ctx={ctx} /></caption>}
          {b.headRows.length > 0 && (
            <thead>{b.headRows.map((row, r) => <tr key={r}>{row.cells.map(cell)}</tr>)}</thead>
          )}
          <tbody>{b.bodyRows.map((row, r) => <tr key={r}>{row.cells.map(cell)}</tr>)}</tbody>
        </table>
      );
    }
    case "figure":
      return <Figure block={b} ctx={ctx} />;
    case "generic":
      return (
        <div id={b.id}>
          {b.inlines.length > 0 && <p><Inl inlines={b.inlines} ctx={ctx} /></p>}
          <Blocks blocks={b.blocks} ctx={ctx} />
        </div>
      );
    default:
      return null;
  }
}

function Figure({ block: b, ctx }: { block: Extract<Block, { kind: "figure" }>; ctx: RenderCtx }) {
  const src = useImageSrc(b.imageHref);
  const style = b.imageScale ? { maxWidth: `${b.imageScale}%` } : undefined;
  return (
    <div className="figure" id={b.id}>
      {src ? (
        <img src={src} alt="" style={style} />
      ) : (
        <div className="frame">{b.imageHref ? `[ ${b.imageHref} ]` : "[ figure ]"}</div>
      )}
      {b.caption && <div className="cap"><Inl inlines={b.caption} ctx={ctx} /></div>}
    </div>
  );
}
