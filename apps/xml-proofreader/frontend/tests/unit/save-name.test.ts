import { describe, it, expect } from "vitest";
import { suggestedSaveName } from "../../src/ui/store";

describe("suggestedSaveName (F8)", () => {
  it("preserves .dita extension", () => {
    expect(suggestedSaveName("procedure.dita", null)).toBe("procedure_reviewed.dita");
  });

  it("preserves .xml extension", () => {
    expect(suggestedSaveName("guide.xml", null)).toBe("guide_reviewed.xml");
  });

  it("preserves .ditamap extension", () => {
    expect(suggestedSaveName("manual.ditamap", null)).toBe("manual_reviewed.ditamap");
  });

  it("falls back to .xml when fileName has no extension", () => {
    expect(suggestedSaveName("nodotfile", null)).toBe("nodotfile_reviewed.xml");
  });

  it("falls back to .xml when fileName is null", () => {
    expect(suggestedSaveName(null, null)).toBe("document_reviewed.xml");
  });

  it("returns fileName as-is when saveUri is already bound", () => {
    expect(suggestedSaveName("proc.dita", "fsa:proc_reviewed.dita")).toBe("proc.dita");
  });

  it("handles names with multiple dots correctly (takes last extension)", () => {
    expect(suggestedSaveName("my.topic.dita", null)).toBe("my.topic_reviewed.dita");
  });
});
