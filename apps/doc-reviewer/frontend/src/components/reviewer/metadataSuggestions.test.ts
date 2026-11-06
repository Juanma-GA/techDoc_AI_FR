import { describe, expect, it } from "vitest";

import type { ClientMappingField } from "../../hooks/useClientConfig";
import { resetMappingWithSuggestions } from "./metadataSuggestions";

const fields: Record<string, ClientMappingField> = {
  meta_revision_number: { type: "string", required: true },
  meta_update_type: { type: "enum", required: false, allowed_values: ["Migration", "MCO"] },
};

const suggestions = {
  pages_scanned: 20,
  meta_cmm_number: null,
  meta_pnr_number: [],
  meta_revision_number: "005",
  meta_revision_date: null,
  meta_first_issue_date: null,
};

describe("resetMappingWithSuggestions", () => {
  it("fills the update type suggested by the norm", () => {
    const draft = resetMappingWithSuggestions(fields, { ...suggestions, meta_update_type: "Migration" });

    expect(draft).toMatchObject({ meta_revision_number: "005", meta_update_type: "Migration" });
  });

  it("ignores an update type outside the allowed values or absent", () => {
    expect(resetMappingWithSuggestions(fields, { ...suggestions, meta_update_type: "Other" })).toMatchObject({
      meta_update_type: "",
    });
    expect(resetMappingWithSuggestions(fields, suggestions)).toMatchObject({ meta_update_type: "" });
  });
});
