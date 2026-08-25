// Shared table builder. Produces a TableModel with column/row spans from CALS
// tables (DITA <table>/<tgroup>, S1000D <table>) and from DITA <simpletable>.
// CALS spans: an <entry> with @namest/@nameend spans columns (resolved through
// <colspec> @colname/@colnum); @morerows spans rows.
import type { PosNode } from "../model/types";
import type { Inline, TableCell, TableRow } from "./model";
import { buildInlines } from "./inlines";

export interface TableData {
  caption: Inline[] | null;
  columns: number;
  headRows: TableRow[];
  bodyRows: TableRow[];
}

function childElems(el: PosNode | null, name: RegExp): PosNode[] {
  return el ? (el.children ?? []).filter((c) => c.kind === "element" && name.test(c.name ?? "")) : [];
}
function firstChild(el: PosNode, name: string): PosNode | null {
  return (el.children ?? []).find((c) => c.kind === "element" && c.name === name) ?? null;
}

export function buildTableBlock(tableEl: PosNode): TableData {
  const titleEl = firstChild(tableEl, "title");
  const caption = titleEl ? buildInlines(titleEl.children ?? []) : null;
  const tgroup = firstChild(tableEl, "tgroup");
  if (tgroup) return { caption, ...buildCals(tgroup) };
  return { caption, ...buildSimple(tableEl) };
}

function buildCals(tgroup: PosNode): Omit<TableData, "caption"> {
  // colname -> 1-based column number
  const colNum = new Map<string, number>();
  childElems(tgroup, /^colspec$/).forEach((cs, i) => {
    const name = cs.attrs?.["colname"] ?? `c${i + 1}`;
    const num = cs.attrs?.["colnum"] ? parseInt(cs.attrs["colnum"], 10) : i + 1;
    colNum.set(name, num);
  });
  const declaredCols = tgroup.attrs?.["cols"] ? parseInt(tgroup.attrs["cols"], 10) : colNum.size;

  const cellsOf = (row: PosNode, header: boolean): TableCell[] =>
    childElems(row, /entry$/).map((entry) => {
      const ns = entry.attrs?.["namest"];
      const ne = entry.attrs?.["nameend"];
      let colSpan = 1;
      if (ns && ne && colNum.has(ns) && colNum.has(ne)) {
        colSpan = Math.max(1, colNum.get(ne)! - colNum.get(ns)! + 1);
      }
      const morerows = entry.attrs?.["morerows"] ? parseInt(entry.attrs["morerows"], 10) : 0;
      return { inlines: buildInlines(entry.children ?? []), colSpan, rowSpan: morerows + 1, header };
    });

  const thead = firstChild(tgroup, "thead");
  const tbody = firstChild(tgroup, "tbody");
  const headRows = childElems(thead, /^row$/).map((r) => ({ cells: cellsOf(r, true) }));
  const bodyParent = tbody ?? tgroup;
  const bodyRows = childElems(bodyParent, /^row$/).map((r) => ({ cells: cellsOf(r, false) }));

  const columns = declaredCols || maxCols([...headRows, ...bodyRows]);
  return { columns, headRows, bodyRows };
}

function buildSimple(tableEl: PosNode): Omit<TableData, "caption"> {
  const headEl = firstChild(tableEl, "sthead");
  const cellsOf = (row: PosNode, header: boolean): TableCell[] =>
    childElems(row, /entry$/).map((e) => ({ inlines: buildInlines(e.children ?? []), colSpan: 1, rowSpan: 1, header }));
  const headRows = headEl ? [{ cells: cellsOf(headEl, true) }] : [];
  const bodyRows = childElems(tableEl, /^strow$/).map((r) => ({ cells: cellsOf(r, false) }));
  const columns = maxCols([...headRows, ...bodyRows]);
  return { columns, headRows, bodyRows };
}

function maxCols(rows: TableRow[]): number {
  return rows.reduce((m, r) => Math.max(m, r.cells.reduce((s, c) => s + c.colSpan, 0)), 0);
}
