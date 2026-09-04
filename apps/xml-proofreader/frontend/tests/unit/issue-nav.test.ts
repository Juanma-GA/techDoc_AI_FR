import { describe, it, expect } from "vitest";
import { findSpanByOffset } from "../../src/ui/viewer/Viewer";

// Build a minimal container using the jsdom environment that vitest provides.
function makeContainer(spans: Array<{ start: number; text: string }>): Element {
  const div = document.createElement("div");
  for (const s of spans) {
    const span = document.createElement("span");
    span.dataset.srcStart = String(s.start);
    span.textContent = s.text;
    div.appendChild(span);
  }
  return div;
}

describe("findSpanByOffset (F5, ADR-0028)", () => {
  it("returns the span whose start equals the target offset exactly", () => {
    const c = makeContainer([{ start: 0, text: "a" }, { start: 10, text: "b" }, { start: 20, text: "c" }]);
    expect((findSpanByOffset(c, 10) as HTMLElement)?.dataset.srcStart).toBe("10");
  });

  it("returns the span whose start is <= target (within-span hit)", () => {
    const c = makeContainer([{ start: 0, text: "a" }, { start: 10, text: "b" }, { start: 20, text: "c" }]);
    // offset 13 falls inside the span at 10
    expect((findSpanByOffset(c, 13) as HTMLElement)?.dataset.srcStart).toBe("10");
  });

  it("returns the last span when offset is beyond all spans", () => {
    const c = makeContainer([{ start: 0, text: "a" }, { start: 10, text: "b" }, { start: 30, text: "c" }]);
    expect((findSpanByOffset(c, 999) as HTMLElement)?.dataset.srcStart).toBe("30");
  });

  it("returns span at 0 when offset is 0", () => {
    const c = makeContainer([{ start: 0, text: "a" }, { start: 10, text: "b" }]);
    expect((findSpanByOffset(c, 0) as HTMLElement)?.dataset.srcStart).toBe("0");
  });

  it("returns null for an empty container", () => {
    const c = makeContainer([]);
    expect(findSpanByOffset(c, 5)).toBeNull();
  });
});
