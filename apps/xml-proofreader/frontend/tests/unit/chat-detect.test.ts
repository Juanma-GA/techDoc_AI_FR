// Unit tests for the AI Chat "detect issues" flow (Chunk 23 / D2).
import { describe, it, expect, beforeEach } from "vitest";
import { useStore } from "../../src/ui/store";

type ChatSeam = { mock: (r: string) => void; reset: () => void; enable: () => void };
type DocReview = { __docreview: { __chat: ChatSeam } };
const chatSeam = () => (window as unknown as DocReview).__docreview.__chat;

const BUF = `<?xml version="1.0" encoding="UTF-8"?>
<task id="t"><taskbody><context><p>Apply 2.5 lbf pressure before service.</p></context></taskbody></task>
`;

describe("detectChatIssues", () => {
  beforeEach(() => {
    useStore.getState().clearChat();
    chatSeam().reset();
    useStore.setState({ chatAvailable: true, issues: [] });
    useStore.getState().loadBuffer(null, "t.dita", BUF);
  });

  it("attaches structured findings to the assistant reply", async () => {
    chatSeam().mock(JSON.stringify({
      findings: [
        { rule: "units", severity: "error", message: "Mixed units.", quote: "Apply 2.5 lbf pressure", replacement: "Apply 11 N pressure" },
      ],
    }));

    await useStore.getState().detectChatIssues("Check grammar");

    const msgs = useStore.getState().chatMessages;
    expect(msgs).toHaveLength(2);
    expect(msgs[0].role).toBe("user");
    const reply = msgs[1];
    expect(reply.role).toBe("assistant");
    expect(reply.findings).toHaveLength(1);
    expect(reply.findings![0].replacement).toBe("Apply 11 N pressure");
    expect(reply.text).toMatch(/Found 1 issue/);
    expect(useStore.getState().chatPending).toBe(false);
  });

  it("reports a parse error as text without findings", async () => {
    chatSeam().mock("not json");
    await useStore.getState().detectChatIssues("Check grammar");
    const reply = useStore.getState().chatMessages.at(-1)!;
    expect(reply.findings).toBeUndefined();
    expect(reply.text).toMatch(/couldn't extract issues/i);
  });

  it("says 'No issues found' on an empty findings array", async () => {
    chatSeam().mock(JSON.stringify({ findings: [] }));
    await useStore.getState().detectChatIssues("Check grammar");
    expect(useStore.getState().chatMessages.at(-1)!.text).toMatch(/no issues found/i);
  });
});

describe("addFindingsToIssues", () => {
  beforeEach(() => {
    useStore.setState({ issues: [], rightMode: "comments" });
    useStore.getState().loadBuffer(null, "t.dita", BUF);
  });

  it("converts findings to anchored issues and switches to the Issues tab", () => {
    useStore.getState().addFindingsToIssues([
      { rule: "units", severity: "error", message: "Mixed units.", quote: "Apply 2.5 lbf pressure", replacement: "Apply 11 N pressure" },
    ]);
    const issues = useStore.getState().issues;
    expect(issues).toHaveLength(1);
    expect(issues[0].source).toBe("proofreader");
    expect(issues[0].suggestion).toBe("Apply 11 N pressure");
    expect(issues[0].anchor).toBeDefined();
    expect(useStore.getState().rightMode).toBe("issues");
  });

  it("appends without dropping existing issues", () => {
    useStore.getState().addFindingsToIssues([{ rule: "r", severity: "info", message: "a", quote: "Apply 2.5 lbf pressure" }]);
    useStore.getState().addFindingsToIssues([{ rule: "r", severity: "info", message: "b", quote: "service" }]);
    expect(useStore.getState().issues).toHaveLength(2);
  });

  it("ignores an empty findings list", () => {
    useStore.getState().addFindingsToIssues([]);
    expect(useStore.getState().issues).toHaveLength(0);
  });
});
