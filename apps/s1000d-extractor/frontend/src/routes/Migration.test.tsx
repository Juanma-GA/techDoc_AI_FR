import { describe, expect, it } from "vitest";

import type { DmrlRow, WizardState } from "../lib/api";
import { hasUnmatchedDmrlDms, needsDmrlReview } from "../lib/wizardReview";
import {
  generationFile,
  getCommonMissingFields,
  isRestorableMigrationInput,
} from "./Migration";

function wizardWithDmrl(dmrl: DmrlRow[]): WizardState {
  return { step: "dmrl", split_level: "chapter", dms: [], dmrl };
}

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

describe("DMRL wizard review", () => {
  it("pauses for missing DMs but ignores unmatched PM titles such as Title 1", () => {
    const title: DmrlRow = {
      index: 0,
      arbo: "1",
      dmc: "",
      title: "Title 1",
      dm_type: "",
      icn: "",
      is_pm_title: true,
      matched: false,
      match_rank: "",
      page: null,
      matched_text: "",
    };
    const missingDm: DmrlRow = {
      ...title,
      index: 1,
      dmc: "DMC-PUMP-A-00-00-00-00A-040A-D",
      title: "Missing DM",
      is_pm_title: false,
    };

    expect(hasUnmatchedDmrlDms(wizardWithDmrl([title, missingDm]))).toBe(true);
    expect(hasUnmatchedDmrlDms(wizardWithDmrl([title]))).toBe(false);
  });

  it("pauses for unresolved InfoCode type conflicts and resumes after a choice", () => {
    const conflict: DmrlRow = {
      index: 1,
      arbo: "1",
      dmc: "DMC-PUMP-A-00-00-00-00A-520A-D",
      title: "Removal Procedure",
      dm_type: "",
      dmrl_type: "Descriptif",
      info_code: "520",
      info_code_schema: "proced",
      info_code_dm_type: "procedural",
      type_conflict: true,
      icn: "",
      is_pm_title: false,
      matched: true,
      match_rank: "exact",
      page: 1,
      matched_text: "Removal Procedure",
    };

    expect(needsDmrlReview(wizardWithDmrl([conflict]))).toBe(true);
    expect(
      needsDmrlReview(wizardWithDmrl([{ ...conflict, dm_type: "procedural" }])),
    ).toBe(false);
  });
});