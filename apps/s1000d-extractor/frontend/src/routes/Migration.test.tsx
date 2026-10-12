import { describe, expect, it } from "vitest";

import { generationFile, getCommonMissingFields, isRestorableMigrationInput } from "./Migration";

describe("restored migration inputs", () => {
  it("restores the PDF and shared resources as generation inputs", () => {
    expect(isRestorableMigrationInput("document")).toBe(true);
    expect(isRestorableMigrationInput("dmrl")).toBe(true);
    expect(isRestorableMigrationInput("dm_header")).toBe(true);
    expect(isRestorableMigrationInput("cir")).toBe(false);
  });

  it("sends the file selected in the input instead of stale state", () => {
    const previouslyRestored = new File(["old"], "old.pdf");
    const currentlyDisplayed = new File(["new"], "new.pdf");

    expect(generationFile(currentlyDisplayed, previouslyRestored)).toBe(currentlyDisplayed);
    expect(generationFile(null, previouslyRestored)).toBe(previouslyRestored);
  });
});

describe("common wizard missing fields", () => {
  it("returns only fields shared by every DM", () => {
    expect(getCommonMissingFields([
      { missing_fields: ["security", "language", "title"] },
      { missing_fields: ["security", "language", "DMC"] },
      { missing_fields: ["security", "language"] },
    ])).toEqual(["security", "language"]);
  });

  it("keeps a single DM's fields on that DM", () => {
    expect(getCommonMissingFields([{ missing_fields: ["security"] }])).toEqual([]);
  });
});