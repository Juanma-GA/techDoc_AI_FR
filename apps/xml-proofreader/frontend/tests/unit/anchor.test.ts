import { describe, it, expect } from "vitest";
import { locateQuote, locateQuotePartial, anchorByQuote } from "../../src/core/issues/anchor";

describe("locateQuote — exact match", () => {
  it("locates a verbatim quote and returns source offsets + needle", () => {
    const buffer = "<task><title>Hello world</title></task>";
    const m = locateQuote(buffer, "Hello world");
    expect(m).toBeDefined();
    expect(m!.startOffset).toBe(buffer.indexOf("Hello world"));
    expect(m!.endOffset).toBe(buffer.indexOf("Hello world") + "Hello world".length);
    expect(m!.quote).toBe("Hello world");
    expect(m!.needle).toBe("Hello world");
  });

  it("returns the first occurrence when the quote repeats", () => {
    expect(locateQuote("hello hello hello", "hello")!.startOffset).toBe(0);
  });

  it("honours opts.from to find a later occurrence", () => {
    const buffer = "hello world hello world";
    const second = locateQuote(buffer, "hello", { from: 1 });
    expect(second!.startOffset).toBe(buffer.indexOf("hello", 1));
  });
});

describe("locateQuote — normalized whitespace", () => {
  it("matches across collapsed whitespace runs (indentation / wrapping)", () => {
    const buffer = "<cmd>Torque   the\n    bolt to 50 Nm.</cmd>";
    const m = locateQuote(buffer, "Torque the bolt to 50 Nm.");
    expect(m).toBeDefined();
    // The source substring keeps the original whitespace…
    expect(m!.quote).toBe("Torque   the\n    bolt to 50 Nm.");
    // …while the needle is normalized for rendered-text matching.
    expect(m!.needle).toBe("Torque the bolt to 50 Nm.");
    expect(buffer.slice(m!.startOffset, m!.endOffset)).toBe(m!.quote);
    expect(m!.quote.includes("<")).toBe(false);
  });

  it("tolerates a trailing/leading-whitespace-only difference", () => {
    const buffer = "<p>alpha beta</p>";
    const m = locateQuote(buffer, "  alpha   beta  ");
    expect(m).toBeDefined();
    expect(m!.quote).toBe("alpha beta");
  });
});

describe("locateQuote — rejects quotes crossing tags", () => {
  it("does not match visible text split by an inline element", () => {
    const buffer = "<p>the quick <b>brown</b> fox</p>";
    expect(locateQuote(buffer, "the quick brown fox")).toBeUndefined();
  });

  it("does not match text spanning two block elements", () => {
    const buffer = "<p>Hello</p><p>World</p>";
    expect(locateQuote(buffer, "Hello World")).toBeUndefined();
  });

  it("rejects a quote that itself contains markup", () => {
    const buffer = "<p>a<b>c</p>";
    expect(locateQuote(buffer, "a<b>c")).toBeUndefined();
  });
});

describe("locateQuote — no match / empty", () => {
  it("returns undefined for an empty or whitespace-only quote", () => {
    expect(locateQuote("some buffer", "")).toBeUndefined();
    expect(locateQuote("some buffer", "   \n  ")).toBeUndefined();
  });

  it("returns undefined when the quote is absent", () => {
    expect(locateQuote("<task>hello</task>", "goodbye")).toBeUndefined();
  });
});

describe("locateQuote — entity + typographic normalization tier (G-Q3, ADR-0032)", () => {
  it("locates a quote containing & when buffer has &amp;", () => {
    const buffer = "<p>Q&amp;A guidelines apply.</p>";
    // AI decoded the entity: quote has "&" but buffer has "&amp;"
    const m = locateQuote(buffer, "Q&A guidelines apply.");
    expect(m).toBeDefined();
    expect(buffer.slice(m!.startOffset, m!.endOffset)).toContain("&amp;");
  });

  it("locates a quote with typographic double quotes when buffer has straight quotes", () => {
    const buffer = '<p>Use the "fast" setting.</p>';
    const m = locateQuote(buffer, "“fast” setting.");
    expect(m).toBeDefined();
    expect(m!.quote).toContain('"fast"');
  });

  it("locates a quote with en-dash when buffer has hyphen", () => {
    const buffer = "<p>Torque range 40-60 Nm.</p>";
    const m = locateQuote(buffer, "Torque range 40–60 Nm.");
    expect(m).toBeDefined();
    expect(m!.quote).toContain("-");
  });

  it("existing tiers still win when they match (normalization is last resort)", () => {
    const buffer = "<p>Simple text here.</p>";
    const m = locateQuote(buffer, "Simple text here.");
    expect(m).toBeDefined();
    expect(m!.needle).toBe("Simple text here."); // no normalization applied
  });
});

describe("locateQuotePartial — longest safe prefix (G2, ADR-0032)", () => {
  it("returns undefined for a single-token quote (nothing to shorten)", () => {
    expect(locateQuotePartial("<p>hello</p>", "world")).toBeUndefined();
  });

  it("returns undefined when no prefix matches at all", () => {
    expect(locateQuotePartial("<p>hello</p>", "foo bar baz")).toBeUndefined();
  });

  it("finds the first token when the quote spans two block elements", () => {
    const buffer = "<p>Hello</p><p>World</p>";
    const m = locateQuotePartial(buffer, "Hello World");
    expect(m).toBeDefined();
    expect(m!.quote).toBe("Hello");
    expect(m!.startOffset).toBe(buffer.indexOf("Hello"));
  });

  it("finds the longest safe prefix for inline-split text", () => {
    // "the quick brown fox" but "brown" is inside <b>; longest safe prefix is "the quick"
    const buffer = "<p>the quick <b>brown</b> fox</p>";
    const m = locateQuotePartial(buffer, "the quick brown fox");
    expect(m).toBeDefined();
    // Prefix must not cross tags and must be actual text content.
    expect(m!.quote).not.toContain("<");
    expect(buffer.slice(m!.startOffset, m!.endOffset)).toBe(m!.quote);
  });

  it("does not match a token that falls inside a tag name", () => {
    // "context Apply" — "context" appears only as a tag name, not text content.
    const buffer =
      '<?xml version="1.0"?><task id="t"><taskbody><context><p>Apply pressure.</p></context></taskbody></task>';
    const m = locateQuotePartial(buffer, "context Apply");
    // "context" is inside <context> tag — should be rejected by isInsideTag.
    // "Apply" is text content and may be found as a 1-token prefix of length 1 is skipped when
    // the full token list has length 2 and only "Apply" is the second token… wait no:
    // tokens = ["context", "Apply"]. len=1 tries prefix ["context"] → inside tag → skip.
    // No valid prefix → undefined.
    expect(m).toBeUndefined();
  });
});

describe("anchorByQuote — compatible wrapper", () => {
  it("returns an AnnotationRange backed by locateQuote", () => {
    const buffer = "<task><title>Hello world</title></task>";
    const a = anchorByQuote(buffer, "Hello world");
    expect(a).toEqual({
      nodePath: [],
      startOffset: buffer.indexOf("Hello world"),
      endOffset: buffer.indexOf("Hello world") + "Hello world".length,
      quote: "Hello world",
    });
  });

  it("returns undefined for empty quote and for no match", () => {
    expect(anchorByQuote("some buffer", "")).toBeUndefined();
    expect(anchorByQuote("<task>hello</task>", "goodbye")).toBeUndefined();
  });
});
