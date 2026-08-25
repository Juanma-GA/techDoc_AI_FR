import { describe, it, expect, beforeEach } from "vitest";
import { useStore } from "../../src/ui/store";
import type { Issue } from "../../src/core/issues/types";
import { SupportProvider, SchemaProvider } from "../../src/core/issues/providers";
import { anchorByQuote } from "../../src/core/issues/anchor";

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const DITA_WITH_ID = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE task PUBLIC "-//OASIS//DTD DITA Task//EN" "task.dtd">
<task id="t1">
  <title>Brake adjustment</title>
  <taskbody>
    <steps><step><cmd>Torque the bolt to 50 Nm.</cmd></step></steps>
  </taskbody>
</task>`;

const DITA_WITHOUT_ID = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE task PUBLIC "-//OASIS//DTD DITA Task//EN" "task.dtd">
<task>
  <title>Brake adjustment</title>
  <taskbody><steps><step><cmd>Do something.</cmd></step></steps></taskbody>
</task>`;

const UNSUPPORTED_XML = `<?xml version="1.0"?>
<book xmlns="http://docbook.org/ns/docbook" version="5.0">
  <title>DocBook document</title>
</book>`;

const S1000D_WITH_IDENT = `<?xml version="1.0" encoding="UTF-8"?>
<dmodule>
  <identAndStatusSection>
    <dmAddress><dmIdent><dmCode modelIdentCode="ACME" systemDiffCode="A" systemCode="00" subSystemCode="0" subSubSystemCode="0" assyCode="00" disassyCode="00" disassyCodeVariant="A" infoCode="040" infoCodeVariant="A" itemLocationCode="A"/></dmIdent></dmAddress>
  </identAndStatusSection>
  <content><refs/></content>
</dmodule>`;

const S1000D_WITHOUT_IDENT = `<?xml version="1.0" encoding="UTF-8"?>
<dmodule>
  <content><refs/></content>
</dmodule>`;

// ---------------------------------------------------------------------------
// anchorByQuote
// ---------------------------------------------------------------------------

describe("anchorByQuote", () => {
  it("returns correct offsets when quote is found", () => {
    const buffer = "<task><title>Hello world</title></task>";
    const anchor = anchorByQuote(buffer, "Hello world");
    expect(anchor).toBeDefined();
    expect(anchor!.startOffset).toBe(buffer.indexOf("Hello world"));
    expect(anchor!.endOffset).toBe(buffer.indexOf("Hello world") + "Hello world".length);
    expect(anchor!.quote).toBe("Hello world");
  });

  it("returns undefined for empty quote", () => {
    expect(anchorByQuote("some buffer", "")).toBeUndefined();
  });

  it("returns undefined when quote is not in buffer", () => {
    expect(anchorByQuote("<task>hello</task>", "goodbye")).toBeUndefined();
  });

  it("anchors at the first occurrence when quote appears multiple times", () => {
    const buffer = "hello hello hello";
    const anchor = anchorByQuote(buffer, "hello");
    expect(anchor!.startOffset).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// SupportProvider
// ---------------------------------------------------------------------------

describe("SupportProvider", () => {
  const provider = new SupportProvider();

  it("is always available", () => {
    expect(provider.isAvailable()).toBe(true);
  });

  it("returns no issues for a valid DITA document", async () => {
    const issues = await provider.run(DITA_WITH_ID);
    expect(issues).toHaveLength(0);
  });

  it("returns no issues for a valid S1000D document", async () => {
    const issues = await provider.run(S1000D_WITH_IDENT);
    expect(issues).toHaveLength(0);
  });

  it("returns no issues for an unsupported language (surfaced via store.languageError instead)", async () => {
    // Unsupported-language errors are shown by the Viewer overlay and the
    // Issues tab header via store.languageError — not as a duplicate issue card.
    const issues = await provider.run(UNSUPPORTED_XML);
    expect(issues).toHaveLength(0);
  });

  it("always returns an empty array regardless of input", async () => {
    expect(await provider.run("<doc/>")).toHaveLength(0);
    expect(await provider.run("")).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// SchemaProvider
// ---------------------------------------------------------------------------

describe("SchemaProvider", () => {
  const provider = new SchemaProvider();

  it("is always available", () => {
    expect(provider.isAvailable()).toBe(true);
  });

  it("returns no issues for a DITA task with @id", async () => {
    const issues = await provider.run(DITA_WITH_ID);
    expect(issues).toHaveLength(0);
  });

  it("returns a warning for a DITA task without @id", async () => {
    const issues = await provider.run(DITA_WITHOUT_ID);
    expect(issues).toHaveLength(1);
    expect(issues[0].source).toBe("schema");
    expect(issues[0].severity).toBe("warning");
    expect(issues[0].message).toContain("@id");
  });

  it("returns no issues for unsupported languages (SupportProvider handles those)", async () => {
    const issues = await provider.run(UNSUPPORTED_XML);
    expect(issues).toHaveLength(0);
  });

  it("returns no issues for S1000D with identAndStatusSection", async () => {
    const issues = await provider.run(S1000D_WITH_IDENT);
    expect(issues).toHaveLength(0);
  });

  it("returns a warning for S1000D without identAndStatusSection", async () => {
    const issues = await provider.run(S1000D_WITHOUT_IDENT);
    expect(issues).toHaveLength(1);
    expect(issues[0].source).toBe("schema");
    expect(issues[0].severity).toBe("warning");
    expect(issues[0].message).toContain("identAndStatusSection");
  });
});

// ---------------------------------------------------------------------------
// Store actions: acceptSuggestion / ignoreIssue
// ---------------------------------------------------------------------------

const DITA_BUF = `<?xml version="1.0" encoding="UTF-8"?>
<task id="t1">
  <title>Tighten the bolt to 50 Nm.</title>
  <taskbody><steps><step><cmd>Apply torque.</cmd></step></steps></taskbody>
</task>`;

function makeIssue(overrides: Partial<Issue> = {}): Issue {
  return {
    id: "test-issue-1",
    source: "schema",
    severity: "warning",
    message: "Test issue",
    ...overrides,
  };
}

describe("store — ignoreIssue", () => {
  beforeEach(() => {
    useStore.getState().loadBuffer(null, "t.dita", DITA_BUF);
    useStore.getState().setIssues([makeIssue()]);
  });

  it("removes the issue from the list without touching the buffer", () => {
    const before = useStore.getState().buffer;
    useStore.getState().ignoreIssue("test-issue-1");
    expect(useStore.getState().issues).toHaveLength(0);
    expect(useStore.getState().buffer).toBe(before);
  });

  it("ignoring a non-existent id is a no-op", () => {
    useStore.getState().ignoreIssue("no-such-id");
    expect(useStore.getState().issues).toHaveLength(1);
  });
});

describe("store — acceptSuggestion", () => {
  beforeEach(() => {
    useStore.getState().loadBuffer(null, "t.dita", DITA_BUF);
  });

  it("anchors a comment carrying the suggestion without editing the text (E3)", () => {
    const quote = "50 Nm";
    const suggestion = "55 Nm";
    useStore.getState().setIssues([makeIssue({ quote, suggestion })]);

    useStore.getState().acceptSuggestion("test-issue-1");

    // E3 (ADR-0020): the document text is untouched; a comment is added.
    expect(useStore.getState().buffer).toContain("50 Nm");
    expect(useStore.getState().buffer).toContain("oxy_comment_start");
    expect(useStore.getState().buffer).toContain("55 Nm"); // suggestion in comment body
    expect(useStore.getState().comments).toHaveLength(1);
    expect(useStore.getState().issues).toHaveLength(0);
    expect(useStore.getState().dirty).toBe(true);
  });

  it("is a no-op when issue has no suggestion", () => {
    useStore.getState().setIssues([makeIssue({ quote: "50 Nm" })]);
    const before = useStore.getState().buffer;
    useStore.getState().acceptSuggestion("test-issue-1");
    expect(useStore.getState().buffer).toBe(before);
    expect(useStore.getState().issues).toHaveLength(1);
  });

  it("is a no-op when the quote is not found in the buffer", () => {
    useStore.getState().setIssues([makeIssue({ quote: "not in buffer", suggestion: "replacement" })]);
    const before = useStore.getState().buffer;
    useStore.getState().acceptSuggestion("test-issue-1");
    expect(useStore.getState().buffer).toBe(before);
    expect(useStore.getState().issues).toHaveLength(1);
  });
});
