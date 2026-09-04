import { describe, it, expect, beforeEach } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { useStore } from "../../src/ui/store";

const GOLDEN = readFileSync(join(__dirname, "..", "golden", "oxygen-thread.dita"), "utf8");
const ROOT_ID = "q52_qnb_qjc";
const NESTED_GOLDEN = readFileSync(join(__dirname, "..", "golden", "oxygen-nested-thread.dita"), "utf8");

function root() {
  const r = useStore.getState().comments.find((c) => c.id === ROOT_ID);
  if (!r) throw new Error("thread root not found");
  return r;
}
function simple() {
  const c = useStore.getState().comments.find((x) => x.text.includes("Esta palabra"));
  if (!c) throw new Error("simple comment not found");
  return c;
}

describe("Chunk 5 — thread-aware store mutations (ADR-0007)", () => {
  beforeEach(() => {
    useStore.getState().loadBuffer(null, "oxygen-thread.dita", GOLDEN);
  });

  it("parses the golden thread: root with 2 replies + 2 standalone comments", () => {
    expect(useStore.getState().comments).toHaveLength(3);
    expect(root().replies).toHaveLength(2);
  });

  it("reply() appends a reply and preserves the existing ones", () => {
    useStore.getState().reply(ROOT_ID, "Tercera respuesta");
    const r = root();
    expect(r.replies).toHaveLength(3);
    expect(r.replies![0].text).toBe("De hecho esta bien.");
    expect(r.replies![1].text).toBe("Me parece a mi que no lo esta.");
    expect(r.replies![2].text).toBe("Tercera respuesta");
    expect(useStore.getState().buffer).toContain('comment="Tercera respuesta"');
  });

  it("resolving the root does NOT destroy the replies (the core regression)", () => {
    useStore.getState().toggleResolve(ROOT_ID);
    const r = root();
    expect(r.resolved).toBe(true);
    expect(r.replies).toHaveLength(2);
    expect(r.replies![0].text).toBe("De hecho esta bien.");
    // Other annotations in the document are untouched.
    expect(useStore.getState().buffer).toContain("Esta palabra no me gusta");
    expect(useStore.getState().buffer).toContain("Resuelto estara");
  });

  it("resolving/reopening a single reply leaves siblings and root intact", () => {
    const replyId = root().replies![0].id;
    useStore.getState().toggleResolve(replyId);
    let r = root();
    expect(r.replies![0].resolved).toBe(true);
    expect(r.replies![1].resolved).toBe(false);
    expect(r.resolved).toBe(false);
    expect(r.replies).toHaveLength(2);

    // Reopen the same reply.
    useStore.getState().toggleResolve(root().replies![0].id);
    r = root();
    expect(r.replies![0].resolved).toBe(false);
    expect(r.replies).toHaveLength(2);
  });

  it("editing a reply's text preserves the other reply", () => {
    const replyId = root().replies![1].id;
    useStore.getState().startEdit(replyId);
    useStore.getState().setEditingText("Texto editado");
    useStore.getState().commitEdit();
    const r = root();
    expect(r.replies).toHaveLength(2);
    expect(r.replies![0].text).toBe("De hecho esta bien.");
    expect(r.replies![1].text).toBe("Texto editado");
  });

  it("deleting a reply keeps the root and the other reply", () => {
    const replyId = root().replies![0].id;
    useStore.getState().deleteComment(replyId);
    const r = root();
    expect(r.replies).toHaveLength(1);
    expect(r.replies![0].text).toBe("Me parece a mi que no lo esta.");
    // Root and its anchored text survive.
    expect(useStore.getState().buffer).toContain('id="q52_qnb_qjc"');
    expect(useStore.getState().buffer).toContain("procedimiento describe");
  });

  it("replying to a simple comment converts it into a thread root with an Oxygen id", () => {
    const before = simple();
    expect(before.replies?.length ?? 0).toBe(0);
    expect(before.id.startsWith("c:")).toBe(true);

    useStore.getState().reply(before.id, "Una respuesta");
    const after = simple();
    expect(after.replies).toHaveLength(1);
    expect(after.replies![0].text).toBe("Una respuesta");
    expect(after.id.startsWith("c:")).toBe(false); // gained an Oxygen-style id
    expect(useStore.getState().buffer).toContain(`parentID="${after.id}"`);
  });

  it("records session state-change history on resolve/reopen", () => {
    useStore.getState().toggleResolve(ROOT_ID); // resolved
    useStore.getState().toggleResolve(ROOT_ID); // reopened
    const hist = useStore.getState().history[ROOT_ID];
    expect(hist).toHaveLength(2);
    expect(hist[0].status).toBe("resolved");
    expect(hist[1].status).toBe("open");
  });
});

// ---------------------------------------------------------------------------
// C7 — locate() recursive + reply() mints Oxygen id for synthetic parents
// ---------------------------------------------------------------------------
describe("C7 — nested reply mutations (locate recursive + id minting)", () => {
  beforeEach(() => {
    useStore.getState().loadBuffer(null, "oxygen-nested-thread.dita", NESTED_GOLDEN);
  });

  it("locate() finds a depth-2 nested reply via startEdit", () => {
    // mid=2 is nested under reply1 (tfw_nst_tst), not a direct child of root
    const nestedId = useStore.getState().comments[0].replies![0].replies![0].id;
    useStore.getState().startEdit(nestedId);
    expect(useStore.getState().editingId).toBe(nestedId);
    useStore.getState().cancelEdit();
  });

  it("reply() to depth-2 nested reply: tree survives re-parse, no synthetic c: in XML", () => {
    // mid=2 has no Oxygen id — its id in the model is synthetic (c:...)
    const nestedReply = useStore.getState().comments[0].replies![0].replies![0];
    expect(nestedReply.id.startsWith("c:")).toBe(true);

    useStore.getState().reply(nestedReply.id, "Respuesta de tercer nivel");

    const buffer = useStore.getState().buffer;
    // No synthetic c: ids may appear as parentID in the serialized XML
    expect(buffer).not.toContain('parentID="c:');
    expect(buffer).toContain('comment="Respuesta de tercer nivel"');

    // Re-parse: the full tree must be intact
    const comments = useStore.getState().comments;
    expect(comments).toHaveLength(1);
    const root = comments[0];
    expect(root.id).toBe("z2b_nst_tst");
    expect(root.replies).toHaveLength(2); // mid=1 and mid=3 direct children

    const reply1 = root.replies![0];
    expect(reply1.id).toBe("tfw_nst_tst");
    // mid=2 should now carry a real Oxygen id (minted) and have the new depth-3 reply
    const mid2 = reply1.replies![0];
    expect(mid2.id.startsWith("c:")).toBe(false);
    expect(mid2.replies).toHaveLength(1);
    expect(mid2.replies![0].text).toBe("Respuesta de tercer nivel");
  });
});
