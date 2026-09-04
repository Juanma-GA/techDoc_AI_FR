import { describe, it, expect } from "vitest";
import { defaultSettings, languageMismatch, type Project } from "../../src/core/workspace/types";

const dita: Project = { id: "p", name: "DITA proj", language: "DITA", issue: "1.3", repositoryRef: "x" };
const s1000d: Project = { id: "q", name: "S1000D proj", language: "S1000D", issue: "4.0", repositoryRef: "y" };

describe("B3 — project / workspace validation", () => {
  it("seeds two default projects with a current selection", () => {
    const s = defaultSettings();
    expect(s.projects.length).toBe(2);
    expect(s.projects.some((p) => p.language === "DITA")).toBe(true);
    expect(s.projects.some((p) => p.language === "S1000D")).toBe(true);
    expect(s.projects.some((p) => p.id === s.currentProjectId)).toBe(true);
  });

  it("no document loaded ⇒ no mismatch", () => {
    expect(languageMismatch("", "", dita)).toBe(false);
  });

  it("matching language and issue ⇒ no mismatch", () => {
    expect(languageMismatch("DITA", "1.3", dita)).toBe(false);
    expect(languageMismatch("S1000D", "4.0", s1000d)).toBe(false);
  });

  it("different language ⇒ mismatch", () => {
    expect(languageMismatch("S1000D", "4.0", dita)).toBe(true);
  });

  it("same language, different issue ⇒ mismatch", () => {
    expect(languageMismatch("S1000D", "4.1", s1000d)).toBe(true);
  });

  it("unknown detected version is lenient (no false mismatch)", () => {
    expect(languageMismatch("S1000D", "", s1000d)).toBe(false);
  });
});
