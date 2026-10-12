import { describe, expect, it } from "vitest";

import { getCommonMissingFields, isRestorableMigrationInput } from "./Migration";

describe("restored migration inputs", () => {
  it("restores shared resources but requires an explicit PDF selection", () => {
    expect(isRestorableMigrationInput("document")).toBe(false);
    expect(isRestorableMigrationInput("dmrl")).toBe(true);
    expect(isRestorableMigrationInput("dm_header")).toBe(true);
    expect(isRestorableMigrationInput("cir")).toBe(false);
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