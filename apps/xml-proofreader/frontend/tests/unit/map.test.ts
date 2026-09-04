import { describe, it, expect, vi } from "vitest";
import { parseXml } from "../../src/core/xml/parse";
import { parseMap, mapOutline, mapHrefs, isMapRoot } from "../../src/core/map/model";
import { buildMergedDoc } from "../../src/core/map/merge";

const DITA_MAP = `<?xml version="1.0" encoding="UTF-8"?>
<map>
  <title>Test Map</title>
  <topicref href="intro.dita" navtitle="Introduction">
    <topicref href="intro-detail.dita" navtitle="Details"/>
  </topicref>
  <chapter href="chapter1.dita" navtitle="Chapter One"/>
  <keydef keys="prodname" href="product.dita"/>
</map>`;

const S1000D_PM = `<?xml version="1.0" encoding="UTF-8"?>
<pm>
  <pmTitle>Test PM</pmTitle>
  <content>
    <pmEntry>
      <pmEntryTitle>Section A</pmEntryTitle>
      <dmRef>
        <dmRefIdent>
          <dmCode modelIdentCode="AAA" systemDiffCode="00" systemCode="00" subSystemCode="0" subSubSystemCode="0"/>
        </dmRefIdent>
        <dmTitle><techName>Module</techName><infoName>Info</infoName></dmTitle>
      </dmRef>
    </pmEntry>
  </content>
</pm>`;

const SIMPLE_TOPIC = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="intro">
  <title>Introduction</title>
  <body><p>Hello world.</p></body>
</topic>`;

describe("isMapRoot", () => {
  it("detects DITA map", () => {
    const tree = parseXml(DITA_MAP);
    expect(isMapRoot(tree)).toBe("dita");
  });

  it("detects S1000D PM", () => {
    const tree = parseXml(S1000D_PM);
    expect(isMapRoot(tree)).toBe("s1000d-pm");
  });

  it("returns null for non-map DITA topic", () => {
    const tree = parseXml(SIMPLE_TOPIC);
    expect(isMapRoot(tree)).toBeNull();
  });
});

describe("parseMap — DITA", () => {
  it("extracts title and kind", () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    expect(map.kind).toBe("dita");
    expect(map.title).toBe("Test Map");
  });

  it("builds node hierarchy with hrefs (keydef excluded)", () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    // keydef is excluded from nodes
    expect(map.nodes).toHaveLength(2);
    expect(map.nodes[0].title).toBe("Introduction");
    expect(map.nodes[0].href).toBe("intro.dita");
    expect(map.nodes[1].title).toBe("Chapter One");
    expect(map.nodes[1].href).toBe("chapter1.dita");
  });

  it("nests child topicrefs under their parent", () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    expect(map.nodes[0].children).toHaveLength(1);
    expect(map.nodes[0].children[0].title).toBe("Details");
    expect(map.nodes[0].children[0].href).toBe("intro-detail.dita");
  });

  it("collects keydefs into the keydef map", () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    expect(map.keydefs["prodname"]).toBeDefined();
    expect(map.keydefs["prodname"].href).toBe("product.dita");
  });
});

describe("parseMap — S1000D PM", () => {
  it("extracts title and kind", () => {
    const tree = parseXml(S1000D_PM);
    const map = parseMap(tree, S1000D_PM);
    expect(map.kind).toBe("s1000d-pm");
    expect(map.title).toBe("Test PM");
  });

  it("builds pmEntry → dmRef hierarchy", () => {
    const tree = parseXml(S1000D_PM);
    const map = parseMap(tree, S1000D_PM);
    expect(map.nodes).toHaveLength(1);
    expect(map.nodes[0].title).toBe("Section A");
    expect(map.nodes[0].href).toBeNull();
    expect(map.nodes[0].children).toHaveLength(1);
    expect(map.nodes[0].children[0].title).toContain("Module");
  });

  it("derives filename from dmCode attributes", () => {
    const tree = parseXml(S1000D_PM);
    const map = parseMap(tree, S1000D_PM);
    const dmNode = map.nodes[0].children[0];
    expect(dmNode.href).toBe("DMC-AAA-00-00-0-0.xml");
  });
});

describe("mapOutline", () => {
  it("flattens hierarchy with correct indentation levels", () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    const outline = mapOutline(map.nodes);
    expect(outline[0]).toMatchObject({ title: "Introduction", level: 1, href: "intro.dita" });
    expect(outline[1]).toMatchObject({ title: "Details", level: 2, href: "intro-detail.dita" });
    expect(outline[2]).toMatchObject({ title: "Chapter One", level: 1, href: "chapter1.dita" });
  });

  it("preserves depth-first document order", () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    const titles = mapOutline(map.nodes).map((o) => o.title);
    expect(titles).toEqual(["Introduction", "Details", "Chapter One"]);
  });

  it("uses a custom starting level", () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    const outline = mapOutline(map.nodes, 2);
    expect(outline[0].level).toBe(2);
    expect(outline[1].level).toBe(3);
  });
});

describe("mapHrefs", () => {
  it("returns hrefs in depth-first order", () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    const hrefs = mapHrefs(map.nodes);
    expect(hrefs).toEqual(["intro.dita", "intro-detail.dita", "chapter1.dita"]);
  });

  it("excludes null hrefs (e.g. topichead / pmEntry)", () => {
    const tree = parseXml(S1000D_PM);
    const map = parseMap(tree, S1000D_PM);
    const hrefs = mapHrefs(map.nodes);
    // Section A pmEntry has no href; its dmRef child does
    expect(hrefs).toHaveLength(1);
    expect(hrefs[0]).toBe("DMC-AAA-00-00-0-0.xml");
  });
});

describe("buildMergedDoc", () => {
  it("uses map title as the merged doc title", async () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    const doc = await buildMergedDoc(map, async () => null);
    const title = doc.title?.map((i) => i.text).join("") ?? "";
    expect(title).toBe("Test Map");
  });

  it("shows placeholder blocks for unresolvable hrefs", async () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    const doc = await buildMergedDoc(map, async () => null);
    const placeholders = doc.blocks.filter(
      (b) => b.kind === "note" && b.id.startsWith("missing-"),
    );
    expect(placeholders.length).toBeGreaterThan(0);
  });

  it("renders resolved topics as heading blocks", async () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    const provide = vi.fn(async (href: string) => href === "intro.dita" ? SIMPLE_TOPIC : null);
    const doc = await buildMergedDoc(map, provide);
    expect(doc.blocks.some((b) => b.kind === "heading")).toBe(true);
  });

  it("adds outline entries for resolved topics", async () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    const provide = async (href: string) => href === "intro.dita" ? SIMPLE_TOPIC : null;
    const doc = await buildMergedDoc(map, provide);
    expect(doc.outline.length).toBeGreaterThan(0);
    expect(doc.outline.some((o) => o.text.includes("Introduction"))).toBe(true);
  });

  it("calls provide once per href in mapHrefs order", async () => {
    const tree = parseXml(DITA_MAP);
    const map = parseMap(tree, DITA_MAP);
    const provide = vi.fn(async (_href: string) => null as string | null);
    await buildMergedDoc(map, provide);
    const calledHrefs = provide.mock.calls.map(([h]) => h);
    expect(calledHrefs).toEqual(mapHrefs(map.nodes));
  });
});
