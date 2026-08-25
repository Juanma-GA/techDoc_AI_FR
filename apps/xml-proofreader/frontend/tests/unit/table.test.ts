import { describe, it, expect } from "vitest";
import { parseXml } from "../../src/core/xml/parse";
import { firstByName } from "../../src/core/xml/tree";
import { buildTableBlock } from "../../src/core/render/table";

const CALS = `<table><title>Spanned</title>
  <tgroup cols="4">
    <colspec colname="c1" colnum="1"/><colspec colname="c2" colnum="2"/>
    <colspec colname="c3" colnum="3"/><colspec colname="c4" colnum="4"/>
    <thead>
      <row><entry>Fastener</entry><entry namest="c2" nameend="c3">Torque</entry><entry>Standard</entry></row>
    </thead>
    <tbody>
      <row><entry>Bolt</entry><entry>120 Nm</entry><entry>10%</entry><entry morerows="1">NT-2024-18</entry></row>
      <row><entry>Plate</entry><entry namest="c2" nameend="c3">spanned body cell</entry></row>
    </tbody>
  </tgroup>
</table>`;

describe("B4 — CALS multi-cell tables", () => {
  const tree = parseXml(CALS);
  const tableEl = firstByName(tree, "table")!;
  const t = buildTableBlock(tableEl);

  it("reads the declared column count", () => {
    expect(t.columns).toBe(4);
  });
  it("spans columns via namest/nameend (header)", () => {
    const cells = t.headRows[0].cells;
    expect(cells.map((c) => c.colSpan)).toEqual([1, 2, 1]);
    expect(cells[1].header).toBe(true);
  });
  it("spans rows via morerows", () => {
    const last = t.bodyRows[0].cells[3];
    expect(last.rowSpan).toBe(2);
  });
  it("spans columns in a body row", () => {
    const cell = t.bodyRows[1].cells[1];
    expect(cell.colSpan).toBe(2);
    expect(cell.inlines.map((i) => i.text).join("")).toBe("spanned body cell");
  });
  it("captures the caption", () => {
    expect(t.caption?.map((i) => i.text).join("")).toBe("Spanned");
  });
});

describe("B4 — simpletable (no spans)", () => {
  const ST = `<simpletable><sthead><stentry>A</stentry><stentry>B</stentry></sthead>
    <strow><stentry>1</stentry><stentry>2</stentry></strow></simpletable>`;
  const tree = parseXml(ST);
  const t = buildTableBlock(firstByName(tree, "simpletable")!);
  it("builds header + body rows with span 1", () => {
    expect(t.headRows[0].cells.length).toBe(2);
    expect(t.bodyRows.length).toBe(1);
    expect(t.bodyRows[0].cells.every((c) => c.colSpan === 1 && c.rowSpan === 1)).toBe(true);
  });
});
