// @vitest-environment node
// F7 (ADR-0027): issuesStore — persist/restore per (user, document) with re-anchoring.
import { describe, it, expect, beforeEach } from "vitest";
import type { StoragePort } from "../../src/ports/StoragePort";
import { issueDocKey, persistIssues, restoreIssues } from "../../src/core/workspace/issuesStore";
import type { Issue } from "../../src/core/issues/types";

class MemStorage implements StoragePort {
  private m = new Map<string, string>();
  async get<T>(k: string): Promise<T | null> {
    const v = this.m.get(k);
    return v ? (JSON.parse(v) as T) : null;
  }
  async set<T>(k: string, v: T): Promise<void> { this.m.set(k, JSON.stringify(v)); }
  async remove(k: string): Promise<void> { this.m.delete(k); }
}

const BUF = `<?xml version="1.0" encoding="UTF-8"?><task id="t"><taskbody><context><p>Apply 2.5 lbf pressure.</p></context></taskbody></task>`;

function makeIssue(over: Partial<Issue> = {}): Issue {
  return {
    id: "i1", source: "proofreader", severity: "warning",
    message: "Mixed units.", quote: "Apply 2.5 lbf pressure",
    ...over,
  };
}

describe("issueDocKey", () => {
  it("returns the URI when provided", () => {
    expect(issueDocKey("fsa:path/to/file.dita", BUF)).toBe("fsa:path/to/file.dita");
  });

  it("returns a hash: prefix when URI is null", () => {
    const key = issueDocKey(null, BUF);
    expect(key).toMatch(/^hash:[0-9a-z]+$/);
  });

  it("produces the same hash for the same buffer", () => {
    expect(issueDocKey(null, BUF)).toBe(issueDocKey(null, BUF));
  });

  it("produces different hashes for different buffers", () => {
    expect(issueDocKey(null, BUF)).not.toBe(issueDocKey(null, BUF + " "));
  });
});

describe("persistIssues / restoreIssues — round-trip", () => {
  let storage: MemStorage;

  beforeEach(() => { storage = new MemStorage(); });

  it("restores issues with re-anchored offsets", async () => {
    const issue = makeIssue();
    await persistIssues(storage, "user1", "doc1", [issue]);
    const restored = await restoreIssues(storage, "user1", "doc1", BUF);
    expect(restored).toHaveLength(1);
    // The restored issue has a fresh anchor from anchorByQuote.
    expect(restored[0].anchor).toBeDefined();
    expect(restored[0].anchor!.quote).toContain("Apply 2.5 lbf pressure");
    // Other fields preserved.
    expect(restored[0].id).toBe("i1");
    expect(restored[0].message).toBe("Mixed units.");
  });

  it("discards issues whose quote cannot be found in the (changed) buffer", async () => {
    const issue = makeIssue({ quote: "text that was deleted" });
    await persistIssues(storage, "user1", "doc1", [issue]);
    const restored = await restoreIssues(storage, "user1", "doc1", BUF);
    expect(restored).toHaveLength(0);
  });

  it("keeps issues without a quote (no anchor to re-validate)", async () => {
    const issue = makeIssue({ quote: undefined });
    await persistIssues(storage, "user1", "doc1", [issue]);
    const restored = await restoreIssues(storage, "user1", "doc1", BUF);
    expect(restored).toHaveLength(1);
    expect(restored[0].anchor).toBeUndefined();
  });

  it("returns empty array when nothing was stored", async () => {
    const restored = await restoreIssues(storage, "user1", "doc1", BUF);
    expect(restored).toHaveLength(0);
  });

  it("isolates (user, document) pairs — different user does not see other's issues", async () => {
    await persistIssues(storage, "userA", "doc1", [makeIssue()]);
    const restored = await restoreIssues(storage, "userB", "doc1", BUF);
    expect(restored).toHaveLength(0);
  });

  it("isolates (user, document) pairs — different doc does not leak", async () => {
    await persistIssues(storage, "user1", "doc1", [makeIssue()]);
    const restored = await restoreIssues(storage, "user1", "doc2", BUF);
    expect(restored).toHaveLength(0);
  });

  it("persists multiple issues and restores them all", async () => {
    const issues = [
      makeIssue({ id: "i1", quote: "Apply 2.5 lbf pressure" }),
      makeIssue({ id: "i2", quote: undefined, source: "oxygen" }),
    ];
    await persistIssues(storage, "u", "d", issues);
    const restored = await restoreIssues(storage, "u", "d", BUF);
    expect(restored).toHaveLength(2);
    expect(restored.map((x) => x.id).sort()).toEqual(["i1", "i2"]);
  });
});
