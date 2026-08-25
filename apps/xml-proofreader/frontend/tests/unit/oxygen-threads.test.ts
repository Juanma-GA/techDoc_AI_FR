import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseXml } from "../../src/core/xml/parse";
import { serializeTree } from "../../src/core/xml/tree";
import { parseComments, type ParsedComment } from "../../src/core/oxygen/parse";
import { deleteAnnotation, buildThreadPiGroups, type ThreadInput } from "../../src/core/oxygen/serialize";
import type { CommentHistoryEntry, CommentHistorySidecar } from "../../src/core/workspace/types";

const golden = (f: string) => readFileSync(join(__dirname, "..", "golden", f), "utf8");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function threadRoot(comments: ParsedComment[]): ParsedComment {
  const root = comments.find((c) => c.id === "q52_qnb_qjc");
  if (!root) throw new Error("thread root not found");
  return root;
}

// ---------------------------------------------------------------------------
// Parse: thread structure
// ---------------------------------------------------------------------------
describe("B7 — Thread parse: structure from oxygen-thread.dita", () => {
  const buffer = golden("oxygen-thread.dita");
  const tree = parseXml(buffer);
  const comments = parseComments(tree, buffer);

  it("returns 3 top-level ParsedComments (root thread + simple + resolved)", () => {
    // thread root, standalone simple, standalone resolved — replies are nested
    expect(comments.length).toBe(3);
  });

  it("thread root has Oxygen id as comment id", () => {
    const root = threadRoot(comments);
    expect(root.author).toBe("jsevillano");
    expect(root.text).toBe("Este procedimiento esta mal.");
    expect(root.resolved).toBe(false);
  });

  it("thread root has exactly 2 replies", () => {
    const root = threadRoot(comments);
    expect(root.replies).toHaveLength(2);
  });

  it("replies carry parentId pointing to root id", () => {
    const root = threadRoot(comments);
    const [r1, r2] = root.replies!;
    expect(r1.parentId).toBe("q52_qnb_qjc");
    expect(r2.parentId).toBe("q52_qnb_qjc");
  });

  it("replies have correct authors and text in document order (mid=1 first)", () => {
    const root = threadRoot(comments);
    const [r1, r2] = root.replies!;
    expect(r1.text).toBe("De hecho esta bien.");
    expect(r2.text).toBe("Me parece a mi que no lo esta.");
  });

  it("replies do not themselves carry replies", () => {
    const root = threadRoot(comments);
    for (const reply of root.replies!) {
      expect(reply.replies?.length ?? 0).toBe(0);
    }
  });

  it("thread root anchor quote contains the shared annotated text", () => {
    const root = threadRoot(comments);
    expect(root.anchor.quote).toContain("Este");
    expect(root.anchor.quote).toContain("procedimiento describe");
  });

  it("simple standalone comment parses unchanged (author, text, resolved=false)", () => {
    const simple = comments.find((c) =>
      c.text.includes("Esta palabra no me gusta")
    )!;
    expect(simple).toBeTruthy();
    expect(simple.author).toBe("jsevillano");
    expect(simple.resolved).toBe(false);
    expect(simple.replies?.length ?? 0).toBe(0);
  });

  it("resolved standalone comment carries resolved=true", () => {
    const resolved = comments.find((c) => c.resolved)!;
    expect(resolved).toBeTruthy();
    expect(resolved.text).toContain("Resuelto");
  });
});

// ---------------------------------------------------------------------------
// Round-trip: deleteAnnotation removes the entire thread block
// ---------------------------------------------------------------------------
describe("B7 — Thread round-trip: deleteAnnotation", () => {
  it("parse → serialize of the thread golden is byte-identical", () => {
    const buffer = golden("oxygen-thread.dita");
    expect(serializeTree(parseXml(buffer), buffer)).toBe(buffer);
  });

  it("deleting thread root removes all stacked opening and closing PIs", () => {
    const buffer = golden("oxygen-thread.dita");
    const tree = parseXml(buffer);
    const comments = parseComments(tree, buffer);
    const root = threadRoot(comments);

    const without = deleteAnnotation(buffer, root.spans);

    // All thread PIs must be gone
    expect(without).not.toContain('id="q52_qnb_qjc"');
    expect(without).not.toContain('parentID="q52_qnb_qjc"');
    expect(without).not.toContain('mid="1"');
    expect(without).not.toContain('mid="2"');
    // The shared annotated text must survive
    expect(without).toContain("Este");
    expect(without).toContain("procedimiento describe");
  });

  it("deleting thread root does not remove the other annotations in the document", () => {
    const buffer = golden("oxygen-thread.dita");
    const tree = parseXml(buffer);
    const comments = parseComments(tree, buffer);
    const root = threadRoot(comments);

    const without = deleteAnnotation(buffer, root.spans);
    // Standalone simple and resolved comments must still be present
    expect(without).toContain("Esta palabra no me gusta");
    expect(without).toContain("Resuelto estara");
  });

  it("spans cover the content between all stacked PIs (contentStart < contentEnd)", () => {
    const buffer = golden("oxygen-thread.dita");
    const tree = parseXml(buffer);
    const root = threadRoot(parseComments(tree, buffer));

    expect(root.spans.openStart).toBeLessThan(root.spans.contentStart);
    expect(root.spans.contentStart).toBeLessThan(root.spans.contentEnd);
    expect(root.spans.contentEnd).toBeLessThan(root.spans.closeEnd);
  });

  it("text recovered from spans matches the quote", () => {
    const buffer = golden("oxygen-thread.dita");
    const tree = parseXml(buffer);
    const root = threadRoot(parseComments(tree, buffer));

    const rawSlice = buffer.slice(root.spans.contentStart, root.spans.contentEnd);
    // The raw slice (shared text + no inner PIs) should contain the annotated text
    expect(rawSlice).toContain("Este");
    expect(rawSlice).toContain("procedimiento describe");
  });
});

// ---------------------------------------------------------------------------
// Serialize: buildThreadPiGroups format
// ---------------------------------------------------------------------------
describe("B7 — buildThreadPiGroups: PI format", () => {
  const ts = Date.UTC(2026, 5, 18, 12, 0, 0);

  it("root PI ends with id= (id is the last attribute)", () => {
    const { open } = buildThreadPiGroups({
      root: { author: "alice", timestamp: ts, text: "Root note", color: "yellow", id: "abc123", resolved: false },
      replies: [],
    });
    // id attribute must appear in the PI
    expect(open).toContain('id="abc123"');
    // id must come after comment=
    const attrPart = open.replace(/^<\?oxy_comment_start /, "").replace(/\?>$/, "");
    expect(attrPart.lastIndexOf('id="abc123"')).toBeGreaterThan(
      attrPart.lastIndexOf('comment=')
    );
  });

  it("root PI with no replies has bare close", () => {
    const { open, close } = buildThreadPiGroups({
      root: { author: "alice", timestamp: ts, text: "Note", color: "yellow", id: "x1", resolved: false },
      replies: [],
    });
    expect(open).toContain("oxy_comment_start");
    expect(close).toBe("<?oxy_comment_end?>");
  });

  it("reply PI contains parentID and mid (mid last)", () => {
    const { open } = buildThreadPiGroups({
      root: { author: "alice", timestamp: ts, text: "Root", color: "yellow", id: "r1", resolved: false },
      replies: [
        { author: "bob", timestamp: ts + 1000, text: "Reply", parentId: "r1", mid: 1, resolved: false },
      ],
    });
    expect(open).toContain('parentID="r1"');
    expect(open).toContain('mid="1"');
    // mid must come after comment= in the reply PI
    const replyPi = open.split("?>")[1] + "?>";  // second PI
    const attrPart = replyPi.replace(/^<\?oxy_comment_start /, "").replace(/\?>$/, "");
    expect(attrPart.lastIndexOf('mid="1"')).toBeGreaterThan(
      attrPart.lastIndexOf('comment=')
    );
  });

  it("close group: replies in reverse mid order, then bare root close", () => {
    const { close } = buildThreadPiGroups({
      root: { author: "alice", timestamp: ts, text: "Root", color: "yellow", id: "r1", resolved: false },
      replies: [
        { author: "bob", timestamp: ts, text: "Reply 1", parentId: "r1", mid: 1 },
        { author: "carol", timestamp: ts, text: "Reply 2", parentId: "r1", mid: 2 },
      ],
    });
    expect(close).toBe('<?oxy_comment_end mid="2"?><?oxy_comment_end mid="1"?><?oxy_comment_end?>');
  });

  it("resolved root emits flag before id", () => {
    const { open } = buildThreadPiGroups({
      root: { author: "alice", timestamp: ts, text: "Note", color: "yellow", id: "r1", resolved: true },
      replies: [],
    });
    expect(open).toContain('flag="done"');
    const attrPart = open.replace(/^<\?oxy_comment_start /, "").replace(/\?>$/, "");
    expect(attrPart.indexOf('flag="done"')).toBeLessThan(attrPart.indexOf('id='));
  });

  it("resolved reply emits flag after mid", () => {
    const { open } = buildThreadPiGroups({
      root: { author: "alice", timestamp: ts, text: "Root", color: "yellow", id: "r1", resolved: false },
      replies: [
        { author: "bob", timestamp: ts, text: "Reply", parentId: "r1", mid: 1, resolved: true },
      ],
    });
    const replyPi = open.split("?>").slice(1).join("?>").trim();
    expect(replyPi).toContain('flag="done"');
    const attrPart = replyPi.replace(/^<\?oxy_comment_start /, "").replace(/\?>.*/, "");
    expect(attrPart.indexOf('flag="done"')).toBeGreaterThan(attrPart.indexOf('mid='));
  });

  it("escapes special characters in comment text", () => {
    const { open } = buildThreadPiGroups({
      root: { author: "a", timestamp: ts, text: 'note & "quoted"', color: "yellow", id: "e1", resolved: false },
      replies: [],
    });
    expect(open).toContain("note &amp; &quot;quoted&quot;");
  });
});

// ---------------------------------------------------------------------------
// State-history sidecar types (ADR-0004)
// ---------------------------------------------------------------------------
describe("B7 — CommentHistorySidecar types", () => {
  it("CommentHistoryEntry can be constructed with expected fields", () => {
    const entry: CommentHistoryEntry = {
      status: "resolved",
      timestamp: Date.UTC(2026, 5, 19, 10, 0, 0),
      author: "jsevillano",
    };
    expect(entry.status).toBe("resolved");
    expect(entry.author).toBe("jsevillano");
  });

  it("CommentHistorySidecar is a keyed record of entry arrays", () => {
    const sidecar: CommentHistorySidecar = {
      "q52_qnb_qjc": [
        { status: "open", timestamp: Date.UTC(2026, 5, 18, 16, 32, 47), author: "jsevillano" },
        { status: "resolved", timestamp: Date.UTC(2026, 5, 19, 9, 0, 0), author: "jsevillano" },
      ],
    };
    expect(sidecar["q52_qnb_qjc"]).toHaveLength(2);
    expect(sidecar["q52_qnb_qjc"][1].status).toBe("resolved");
  });

  it("status is either 'open' or 'resolved'", () => {
    const open: CommentHistoryEntry = { status: "open", timestamp: 0, author: "a" };
    const resolved: CommentHistoryEntry = { status: "resolved", timestamp: 1, author: "b" };
    expect(open.status).toBe("open");
    expect(resolved.status).toBe("resolved");
  });
});

// ---------------------------------------------------------------------------
// C6 — Chunk 15: Color fidelity — hasHighlight, wrapper round-trip, setColor
// ---------------------------------------------------------------------------
describe("C6 — hasHighlight: parser sets flag based on oxy_custom_start presence", () => {
  it("thread root without oxy_custom_start has hasHighlight=false/undefined", () => {
    const buffer = golden("oxygen-thread.dita");
    const tree = parseXml(buffer);
    const comments = parseComments(tree, buffer);
    const root = comments.find((c) => c.id === "q52_qnb_qjc")!;
    // The thread golden has no oxy_custom_start wrapper on the thread root
    expect(root.hasHighlight).toBeFalsy();
  });

  it("simple comment with oxy_custom_start has color parsed from RGB", () => {
    const buffer = golden("task-with-oxygen-comments.dita");
    const tree = parseXml(buffer);
    const comments = parseComments(tree, buffer);
    // All simple annotations in that golden have highlight wrappers
    expect(comments.length).toBeGreaterThan(0);
    // At least one should have a recognized color
    expect(comments.some((c) => c.color !== undefined)).toBe(true);
  });
});

describe("C6 — buildThreadPiGroups: wrapper emitted iff highlight set", () => {
  const ts = Date.UTC(2026, 5, 18, 12, 0, 0);

  const base: ThreadInput = {
    root: { author: "alice", timestamp: ts, text: "Root", color: "yellow", id: "r1", resolved: false },
    replies: [{ author: "bob", timestamp: ts + 1000, text: "Reply", parentId: "r1", mid: 1, resolved: false }],
  };

  it("without highlight: no oxy_custom_start/end in output", () => {
    const { open, close } = buildThreadPiGroups(base);
    expect(open).not.toContain("oxy_custom_start");
    expect(close).not.toContain("oxy_custom_end");
  });

  it("with highlight: oxy_custom_start after root PI in open", () => {
    const { open } = buildThreadPiGroups({ ...base, highlight: "yellow" });
    const rootEnd = open.indexOf("?>");
    const customIdx = open.indexOf("oxy_custom_start");
    expect(customIdx).toBeGreaterThan(rootEnd);
    expect(open).toContain('color="255,243,163"');
  });

  it("with highlight: oxy_custom_end before bare close in close", () => {
    const { close } = buildThreadPiGroups({ ...base, highlight: "green" });
    const customEndIdx = close.indexOf("oxy_custom_end");
    const bareCloseIdx = close.lastIndexOf("<?oxy_comment_end?>");
    expect(customEndIdx).toBeLessThan(bareCloseIdx);
  });

  it("with highlight: reply PIs come after oxy_custom_start", () => {
    const { open } = buildThreadPiGroups({ ...base, highlight: "pink" });
    const customIdx = open.indexOf("oxy_custom_start");
    const replyIdx = open.indexOf("parentID=");
    expect(replyIdx).toBeGreaterThan(customIdx);
  });

  it("round-trip: highlight preserved iff originally present (absent→absent)", () => {
    const buffer = golden("oxygen-thread.dita");
    const tree = parseXml(buffer);
    const comments = parseComments(tree, buffer);
    const root = comments.find((c) => c.id === "q52_qnb_qjc")!;
    // No wrapper in original → none in rebuilt
    const replies = root.replies!.map((r, i) => ({
      author: r.author, timestamp: r.timestamp, text: r.text,
      parentId: root.id, mid: i + 1, resolved: r.resolved,
    }));
    const { open, close } = buildThreadPiGroups({
      root: { author: root.author, timestamp: root.timestamp, text: root.text, color: root.color, id: root.id, resolved: root.resolved },
      replies,
      highlight: root.hasHighlight ? root.color : undefined,
    });
    expect(open).not.toContain("oxy_custom_start");
    expect(close).not.toContain("oxy_custom_end");
  });
});

// ---------------------------------------------------------------------------
// C7 — Chunk 16: Nested replies — parser tree + round-trip byte-identical
// ---------------------------------------------------------------------------
describe("C7 — Nested thread parse: tree structure from oxygen-nested-thread.dita", () => {
  const buffer = golden("oxygen-nested-thread.dita");
  const tree = parseXml(buffer);
  const comments = parseComments(tree, buffer);

  it("returns exactly 1 top-level ParsedComment (the root)", () => {
    expect(comments).toHaveLength(1);
  });

  it("root has Oxygen id z2b_nst_tst and comment text", () => {
    expect(comments[0].id).toBe("z2b_nst_tst");
    expect(comments[0].text).toBe("Comentario raiz.");
  });

  it("root has exactly 2 direct replies (mid=1 and mid=3)", () => {
    expect(comments[0].replies).toHaveLength(2);
  });

  it("first direct reply has Oxygen id and mid=1", () => {
    const reply1 = comments[0].replies![0];
    expect(reply1.id).toBe("tfw_nst_tst");
    expect(reply1.mid).toBe(1);
    expect(reply1.parentId).toBe("z2b_nst_tst");
  });

  it("first direct reply itself has one nested reply (mid=2)", () => {
    const reply1 = comments[0].replies![0];
    expect(reply1.replies).toHaveLength(1);
    const nested = reply1.replies![0];
    expect(nested.mid).toBe(2);
    expect(nested.parentId).toBe("tfw_nst_tst");
    expect(nested.text).toBe("Doble REPLY");
  });

  it("second direct reply is mid=3 direct child of root", () => {
    const reply3 = comments[0].replies![1];
    expect(reply3.mid).toBe(3);
    expect(reply3.parentId).toBe("z2b_nst_tst");
    expect(reply3.text).toBe("De verdad?");
  });

  it("nested reply has no further replies", () => {
    const nested = comments[0].replies![0].replies![0];
    expect((nested.replies ?? []).length).toBe(0);
  });
});

describe("C7 — Nested thread round-trip: byte-identical serialization", () => {
  it("parse → serialize back to byte-identical original", () => {
    const buffer = golden("oxygen-nested-thread.dita");
    const tree = parseXml(buffer);
    const comments = parseComments(tree, buffer);
    const root = comments[0];

    // Flatten all replies in order (depth-first, mid order) for serializer.
    function flattenReplies(replies: import("../../src/core/model/types").Comment[]): import("../../src/core/oxygen/serialize").ReplyInput[] {
      const out: import("../../src/core/oxygen/serialize").ReplyInput[] = [];
      function walk(rs: import("../../src/core/model/types").Comment[]) {
        for (const r of rs) {
          const oxyId = r.id && !r.id.startsWith("c:") ? r.id : undefined;
          out.push({ author: r.author, timestamp: r.timestamp, text: r.text, parentId: r.parentId!, mid: r.mid!, resolved: r.resolved, id: oxyId });
          walk(r.replies ?? []);
        }
      }
      walk(replies);
      return out;
    }

    const replies = flattenReplies(root.replies ?? []);
    const { open, close } = buildThreadPiGroups({
      root: { author: root.author, timestamp: root.timestamp, text: root.text, color: root.color, id: root.id, resolved: root.resolved },
      replies,
    });

    // Verify the PIs are in the buffer at the expected positions.
    const inner = buffer.slice(root.spans.contentStart, root.spans.contentEnd);
    const rebuilt = buffer.slice(0, root.spans.openStart) + open + inner + close + buffer.slice(root.spans.closeEnd);
    expect(rebuilt).toBe(buffer);
  });

  it("close order is mid=2 then mid=3 then mid=1 (depth DESC, mid DESC within same depth)", () => {
    const ts = Date.UTC(2026, 5, 22, 10, 0, 0);
    const { close } = buildThreadPiGroups({
      root: { author: "a", timestamp: ts, text: "Root", color: "yellow", id: "z2b_tst", resolved: false },
      replies: [
        { author: "a", timestamp: ts + 100, text: "Reply1", parentId: "z2b_tst", mid: 1, id: "tfw_tst" },
        { author: "a", timestamp: ts + 200, text: "Nested", parentId: "tfw_tst", mid: 2 },
        { author: "a", timestamp: ts + 300, text: "Direct", parentId: "z2b_tst", mid: 3 },
      ],
    });
    // Expected: mid=2, mid=3, mid=1, bare
    expect(close).toBe('<?oxy_comment_end mid="2"?><?oxy_comment_end mid="3"?><?oxy_comment_end mid="1"?><?oxy_comment_end?>');
  });

  it("reply with Oxygen id emits id= attribute", () => {
    const ts = Date.UTC(2026, 5, 22, 10, 0, 0);
    const { open } = buildThreadPiGroups({
      root: { author: "a", timestamp: ts, text: "Root", color: "yellow", id: "z2b_tst", resolved: false },
      replies: [
        { author: "b", timestamp: ts + 100, text: "Reply", parentId: "z2b_tst", mid: 1, id: "tfw_tst" },
      ],
    });
    expect(open).toContain('id="tfw_tst"');
    // id must come after mid in the reply PI
    const replyPi = open.split("?>")[1] + "?>";
    expect(replyPi.indexOf('id="tfw_tst"')).toBeGreaterThan(replyPi.indexOf('mid="1"'));
  });
});
