import { describe, it, expect, beforeEach } from "vitest";
import { useStore } from "../../src/ui/store";

const BUF = `<?xml version="1.0" encoding="UTF-8"?>
<task id="t"><taskbody><context><p>Tighten the bolt to 120 Nm before service.</p></context></taskbody></task>
`;

function range(quote: string) {
  // Offsets always come from the *current* buffer (as the live DOM would give).
  const buf = useStore.getState().buffer || BUF;
  const start = buf.indexOf(quote);
  return { start, end: start + quote.length, quote };
}

describe("F3 — annotation lifecycle through the store", () => {
  beforeEach(() => {
    useStore.getState().loadBuffer(null, "t.dita", BUF);
  });

  it("adds a highlight and shows it in comments", () => {
    const s = useStore.getState();
    s.addAnnotation(range("120 Nm"), "green", false);
    const cs = useStore.getState().comments;
    expect(cs.length).toBe(1);
    expect(cs[0].color).toBe("green");
    expect(cs[0].anchor.quote).toBe("120 Nm");
    expect(useStore.getState().buffer).toContain('color="189,245,200"');
  });

  it("creates a comment, edits its text live, and reflects it in the XML", () => {
    const s = useStore.getState();
    s.addAnnotation(range("120 Nm"), "pink", true);
    const id = useStore.getState().editingId!;
    expect(id).toBeTruthy();
    s.setEditingText("Should be 130 Nm");
    s.commitEdit();
    const c = useStore.getState().comments[0];
    expect(c.text).toBe("Should be 130 Nm");
    expect(useStore.getState().buffer).toContain('comment="Should be 130 Nm"');
    expect(useStore.getState().buffer).toContain("oxy_comment_start");
  });

  it("changes color, resolves, and deletes restoring the original buffer", () => {
    const s = useStore.getState();
    s.addAnnotation(range("120 Nm"), "yellow", true);
    let id = useStore.getState().editingId!;
    s.setEditingText("check torque");
    s.commitEdit();

    id = useStore.getState().comments[0].id;
    s.setColor(id, "blue");
    expect(useStore.getState().comments[0].color).toBe("blue");

    s.toggleResolve(id);
    expect(useStore.getState().comments[0].resolved).toBe(true);
    expect(useStore.getState().buffer).toContain('flag="done"');

    id = useStore.getState().comments[0].id;
    s.deleteComment(id);
    expect(useStore.getState().comments.length).toBe(0);
    // Non-destructive: removing every annotation restores the file byte for byte.
    expect(useStore.getState().buffer).toBe(BUF);
    expect(useStore.getState().dirty).toBe(true);
  });

  it("keeps the document well-formed and re-parseable after annotating", () => {
    const s = useStore.getState();
    s.addAnnotation(range("bolt"), "yellow", false);
    s.addAnnotation(range("service"), "green", true);
    s.setEditingText("confirm interval");
    s.commitEdit();
    expect(useStore.getState().comments.length).toBe(2);
    // rendered model still builds (no throw) and has blocks
    expect(useStore.getState().rendered.blocks.length).toBeGreaterThan(0);
  });
});
