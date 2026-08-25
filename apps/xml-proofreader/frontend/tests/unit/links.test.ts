import { describe, it, expect, vi } from "vitest";
import { LinkResolver } from "../../src/core/map/links";
import type { MapModel } from "../../src/core/map/model";
import type { PosNode } from "../../src/core/model/types";

// ---- helpers ----------------------------------------------------------------

function keydefs(entries: Record<string, { href?: string; text?: string }>): MapModel["keydefs"] {
  return entries;
}

function makeNode(gi: string, attrs: Record<string, string> = {}, children: PosNode[] = []): PosNode {
  return { kind: "element", name: gi, attrs, start: 0, end: 0, children } as PosNode;
}

function makeCodeNode(
  prefix: "dmCode" | "pmCode",
  parts: { modelIdentCode?: string; systemDiffCode?: string; systemCode?: string }
): PosNode {
  const child = makeNode(prefix, {
    modelIdentCode: parts.modelIdentCode ?? "C159",
    systemDiffCode: parts.systemDiffCode ?? "AAA",
    systemCode: parts.systemCode ?? "00",
  });
  return makeNode(prefix === "dmCode" ? "dmRef" : "pmRef", {}, [child]);
}

function noProvide(): never {
  throw new Error("provide should not be called");
}

// ---- resolveHref ------------------------------------------------------------

describe("LinkResolver.resolveHref", () => {
  it("returns internal for same-doc fragment #id", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    expect(r.resolveHref("#section-1")).toEqual({ kind: "internal", targetId: "section-1" });
  });

  it("returns internal and strips topic path from #topic/section", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    expect(r.resolveHref("#concept/intro")).toEqual({ kind: "internal", targetId: "intro" });
  });

  it("returns external for href without fragment", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    const res = r.resolveHref("other.dita");
    expect(res.kind).toBe("external");
    if (res.kind === "external") {
      expect(res.href).toBe("other.dita");
      expect(res.anchor).toBeUndefined();
    }
  });

  it("returns external with anchor for href with fragment", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    const res = r.resolveHref("other.dita#mytopic/step1");
    expect(res.kind).toBe("external");
    if (res.kind === "external") {
      expect(res.href).toBe("other.dita");
      expect(res.anchor).toBe("step1");
    }
  });

  it("returns unresolved for empty href", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    expect(r.resolveHref("")).toEqual(expect.objectContaining({ kind: "unresolved" }));
  });

  it("resolves keyref from keydefs to internal link", () => {
    const r = new LinkResolver(keydefs({ "safety-note": { href: "#safetySection" } }), noProvide);
    expect(r.resolveHref(undefined, "safety-note")).toEqual({ kind: "internal", targetId: "safetySection" });
  });

  it("resolves keyref from keydefs to external link", () => {
    const r = new LinkResolver(keydefs({ "manual": { href: "ref-manual.dita" } }), noProvide);
    const res = r.resolveHref(undefined, "manual");
    expect(res.kind).toBe("external");
    if (res.kind === "external") expect(res.href).toBe("ref-manual.dita");
  });

  it("falls back to raw href when keyref not found", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    const res = r.resolveHref("fallback.dita", "missing-key");
    // keyref not found but href is provided → use raw href
    expect(res.kind).toBe("external");
    if (res.kind === "external") expect(res.href).toBe("fallback.dita");
  });

  it("returns unresolved when both keyref missing and href empty", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    expect(r.resolveHref("", "missing-key")).toEqual(expect.objectContaining({ kind: "unresolved" }));
  });
});

// ---- resolveKeyref ----------------------------------------------------------

describe("LinkResolver.resolveKeyref", () => {
  it("resolves key with href", () => {
    const r = new LinkResolver(keydefs({ intro: { href: "intro.dita" } }), noProvide);
    const res = r.resolveKeyref("intro");
    expect(res.kind).toBe("external");
    if (res.kind === "external") expect(res.href).toBe("intro.dita");
  });

  it("returns unresolved for unknown key", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    expect(r.resolveKeyref("ghost")).toEqual(expect.objectContaining({ kind: "unresolved" }));
  });

  it("returns unresolved for key with no href", () => {
    const r = new LinkResolver(keydefs({ "prod-name": { text: "SuperTruck" } }), noProvide);
    expect(r.resolveKeyref("prod-name")).toEqual(expect.objectContaining({ kind: "unresolved" }));
  });
});

// ---- resolveConref ----------------------------------------------------------

describe("LinkResolver.resolveConref", () => {
  it("returns internal for same-doc conref #topic/elem", async () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    const res = await r.resolveConref("#mytopic/note-1");
    expect(res).toEqual({ kind: "internal", targetId: "note-1" });
  });

  it("returns unresolved when external file not available", async () => {
    const provide = vi.fn().mockResolvedValue(null);
    const r = new LinkResolver(keydefs({}), provide);
    const res = await r.resolveConref("warnings.dita#safety/warnNote");
    expect(res).toEqual(expect.objectContaining({ kind: "unresolved" }));
    expect(provide).toHaveBeenCalledWith("warnings.dita");
  });

  it("returns conref fragment when external file resolves and element found", async () => {
    const xml = `<topic id="safety"><body><note id="warnNote">Do not touch live wires.</note></body></topic>`;
    const provide = vi.fn().mockResolvedValue(xml);
    const r = new LinkResolver(keydefs({}), provide);
    const res = await r.resolveConref("warnings.dita#safety/warnNote");
    expect(res.kind).toBe("conref");
    if (res.kind === "conref") expect(res.content).toContain("Do not touch");
  });

  it("returns unresolved when element id not found in fetched file", async () => {
    const xml = `<topic id="safety"><body><note id="other">Some text.</note></body></topic>`;
    const provide = vi.fn().mockResolvedValue(xml);
    const r = new LinkResolver(keydefs({}), provide);
    const res = await r.resolveConref("warnings.dita#safety/warnNote");
    expect(res).toEqual(expect.objectContaining({ kind: "unresolved" }));
  });
});

// ---- resolveConkeyref -------------------------------------------------------

describe("LinkResolver.resolveConkeyref", () => {
  it("resolves conkeyref via keydefs + elemId", async () => {
    const xml = `<topic id="shared"><body><note id="n1">Shared note text.</note></body></topic>`;
    const provide = vi.fn().mockResolvedValue(xml);
    const r = new LinkResolver(keydefs({ "shared-warnings": { href: "warnings.dita" } }), provide);
    const res = await r.resolveConkeyref("shared-warnings/n1");
    expect(res.kind).toBe("conref");
    if (res.kind === "conref") expect(res.content).toContain("Shared note text");
  });

  it("returns unresolved for missing key", async () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    const res = await r.resolveConkeyref("unknown-key/elem");
    expect(res).toEqual(expect.objectContaining({ kind: "unresolved" }));
  });
});

// ---- S1000D resolvers -------------------------------------------------------

describe("LinkResolver.resolveS1000dInternalRef", () => {
  it("returns internal for valid internalRefId", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    const node = makeNode("internalRef", { internalRefId: "para-003" });
    expect(r.resolveS1000dInternalRef(node)).toEqual({ kind: "internal", targetId: "para-003" });
  });

  it("returns unresolved when internalRefId is missing", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    const node = makeNode("internalRef", {});
    expect(r.resolveS1000dInternalRef(node)).toEqual(expect.objectContaining({ kind: "unresolved" }));
  });
});

describe("LinkResolver.resolveS1000dExternalRef", () => {
  it("maps dmRef with dmCode to DMC filename", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    const node = makeCodeNode("dmCode", { modelIdentCode: "C159", systemDiffCode: "AAA", systemCode: "72" });
    const res = r.resolveS1000dExternalRef(node);
    expect(res.kind).toBe("external");
    if (res.kind === "external") {
      expect(res.href).toMatch(/^DMC-/);
      expect(res.href).toContain("C159");
      expect(res.href).toContain(".xml");
    }
  });

  it("maps pmRef with pmCode to PMC filename", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    const child = makeNode("pmCode", { modelIdentCode: "S1000D", systemDiffCode: "PM", systemCode: "001" });
    const node = makeNode("pmRef", {}, [child]);
    const res = r.resolveS1000dExternalRef(node);
    expect(res.kind).toBe("external");
    if (res.kind === "external") expect(res.href).toMatch(/^PMC-/);
  });

  it("returns unresolved when no dmCode/pmCode present", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    const node = makeNode("dmRef", {});
    expect(r.resolveS1000dExternalRef(node)).toEqual(expect.objectContaining({ kind: "unresolved" }));
  });

  it("returns unresolved when dmCode has no attributes", () => {
    const r = new LinkResolver(keydefs({}), noProvide);
    const child = makeNode("dmCode", {});
    const node = makeNode("dmRef", {}, [child]);
    expect(r.resolveS1000dExternalRef(node)).toEqual(expect.objectContaining({ kind: "unresolved" }));
  });
});
