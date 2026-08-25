import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseXml } from "../../src/core/xml/parse";
import { detectLanguage, UnsupportedLanguageError } from "../../src/core/lang/registry";

const golden = (f: string) => readFileSync(join(__dirname, "..", "golden", f), "utf8");

describe("B2 — language detection", () => {
  it("detects DITA 1.3", () => {
    const buffer = golden("task-with-oxygen-comments.dita");
    const { detection, profile } = detectLanguage(parseXml(buffer), buffer);
    expect(detection.language).toBe("DITA");
    expect(detection.version).toBe("1.3");
    expect(profile.id).toBe("dita-1.3");
  });

  it("detects a DITA reference via @class without DOCTYPE keyword", () => {
    const buffer = golden("reference-with-trackchanges.dita");
    const { detection } = detectLanguage(parseXml(buffer), buffer);
    expect(detection.language).toBe("DITA");
  });

  it("detects S1000D and refines the issue from the schema location", () => {
    const buffer = golden("s1000d-descriptive.xml");
    const { detection, profile } = detectLanguage(parseXml(buffer), buffer);
    expect(detection.language).toBe("S1000D");
    expect(detection.version).toBe("4.1");
    expect(detection.profileId).toBe("s1000d-4.1");
    expect(profile.id).toBe("s1000d");
  });

  it("supports the four S1000D issues via schema location", () => {
    for (const v of ["3.0", "4.0", "4.1", "4.2"]) {
      const buffer = `<?xml version="1.0"?><dmodule xsi:noNamespaceSchemaLocation="http://www.s1000d.org/S1000D_${v.replace(".", "-")}/x.xsd"><content><description><para>x</para></description></content></dmodule>`;
      const { detection } = detectLanguage(parseXml(buffer), buffer);
      expect(detection.version).toBe(v);
    }
  });

  it("rejects an unsupported language naming it", () => {
    const docbook = `<?xml version="1.0"?><book xmlns="http://docbook.org/ns/docbook" version="5.0"><title>X</title></book>`;
    expect(() => detectLanguage(parseXml(docbook), docbook)).toThrow(UnsupportedLanguageError);
    try {
      detectLanguage(parseXml(docbook), docbook);
    } catch (e) {
      expect((e as UnsupportedLanguageError).detectedName).toBe("DocBook");
    }
  });
});

describe("B2 — S1000D rendering", () => {
  const buffer = golden("s1000d-descriptive.xml");
  const { profile } = detectLanguage(parseXml(buffer), buffer);
  const doc = profile.buildRendered(parseXml(buffer), buffer);

  it("builds a title from techName/infoName", () => {
    expect(doc.title?.map((i) => i.text).join("")).toContain("Motor bogie");
    expect(doc.title?.map((i) => i.text).join("")).toContain("Description");
  });

  it("renders a levelledPara heading and a CALS table", () => {
    expect(doc.outline.map((o) => o.text)).toContain("General");
    const table = doc.blocks.find((b) => b.kind === "table");
    expect(table && table.kind === "table" && table.headRows[0].cells.length).toBe(2);
    expect(table && table.kind === "table" && table.bodyRows.length).toBe(2);
  });

  it("maps warning to a danger note and figure to an ICN reference", () => {
    expect(doc.blocks.some((b) => b.kind === "note" && b.noteType === "danger")).toBe(true);
    const fig = doc.blocks.find((b) => b.kind === "figure");
    expect(fig && fig.kind === "figure" && fig.imageHref).toContain("ICN-FLIRT");
  });
});
