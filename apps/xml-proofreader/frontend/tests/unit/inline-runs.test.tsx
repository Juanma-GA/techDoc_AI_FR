import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { InlineRuns } from "../../src/ui/viewer/InlineRuns";
import type { Inline } from "../../src/core/render/model";
import type { ParsedComment } from "../../src/core/oxygen/parse";

const SPANS = { openStart: 0, contentStart: 1, contentEnd: 4, closeEnd: 5 };

function makeComment(resolved: boolean): ParsedComment {
  return {
    id: "c:1",
    author: "Alice",
    timestamp: 0,
    text: "note",
    color: "yellow",
    resolved,
    anchor: { nodePath: [0], startOffset: 0, endOffset: 3, quote: "foo" },
    replies: [],
    key: 10,
    spans: SPANS,
  };
}

function makeTextRun(commentKey: number): Inline {
  return { kind: "text", text: "hello", srcStart: 0, color: "yellow", commentKey };
}

function makeTextRunNoKey(): Inline {
  return { kind: "text", text: "world", srcStart: 10 };
}

describe("InlineRuns — G1 resolved suppresses color", () => {
  it("renders highlight class when comment is NOT resolved", () => {
    const key = 10;
    const map = new Map([[key, makeComment(false)]]);
    const { container } = render(
      <InlineRuns
        inlines={[makeTextRun(key)]}
        commentsByKey={map}
        activeKey={null}
        onFocus={() => {}}
      />
    );
    const span = container.querySelector("span");
    expect(span?.className).toMatch(/hl/);
    expect(span?.className).toMatch(/c-yellow/);
  });

  it("renders plain span (no hl class) when comment IS resolved", () => {
    const key = 10;
    const map = new Map([[key, makeComment(true)]]);
    const { container } = render(
      <InlineRuns
        inlines={[makeTextRun(key)]}
        commentsByKey={map}
        activeKey={null}
        onFocus={() => {}}
      />
    );
    const span = container.querySelector("span");
    expect(span?.className ?? "").not.toMatch(/hl/);
    expect(span?.className ?? "").not.toMatch(/c-yellow/);
  });

  it("runs without a commentKey are unaffected", () => {
    const { container } = render(
      <InlineRuns
        inlines={[makeTextRunNoKey()]}
        commentsByKey={new Map()}
        activeKey={null}
        onFocus={() => {}}
      />
    );
    const span = container.querySelector("span");
    expect(span?.className ?? "").not.toMatch(/hl/);
  });

  it("orphan commentKey (not in map) renders highlight normally", () => {
    // Run has a commentKey but the comment is not in the map → no crash, color shown.
    const { container } = render(
      <InlineRuns
        inlines={[makeTextRun(99)]}
        commentsByKey={new Map()}
        activeKey={null}
        onFocus={() => {}}
        defaultHighlight="yellow"
      />
    );
    const span = container.querySelector("span");
    expect(span?.className).toMatch(/hl/);
  });
});
