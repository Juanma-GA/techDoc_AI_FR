import { describe, expect, it } from "vitest";

import { findCmmMappingWarning, findInconclusiveResults } from "./IncompleteChecksNotice";
import type { RuleResult } from "../../types/domain";

describe("findInconclusiveResults", () => {
  it("returns the specific checks that did not reach a conclusion", () => {
    const results: RuleResult[] = [
      { rule_id: "RULE_PASS", rule_title: "Passed check", status: "PASS", evidence: null },
      {
        rule_id: "RULE_UNKNOWN",
        rule_title: "Revision date",
        status: "INCONCLUSIVE",
        inconclusive_pages: ["24", "26"],
        evidence: {
          page: "2",
          location: { type: "bbox", bbox: [0, 0, 0, 0] },
          observed_value: null,
          expected_value: null,
        },
      },
      {
        rule_id: "CUSTOM_CMM_MAPPING_SUSPECT",
        status: "INCONCLUSIVE",
        inconclusive_pages: ["1"],
        evidence: null,
      },
      {
        rule_id: "RULE_PARTIAL_FAILURE",
        rule_title: "Bookmark destinations",
        status: "FAIL",
        inconclusive_pages: ["31"],
        evidence: null,
      },
      { rule_id: "RULE_FAIL", rule_title: "Failed check", status: "FAIL", evidence: null },
    ];

    expect(findInconclusiveResults(results).map((result) => result.rule_title)).toEqual([
      "Revision date",
      "Bookmark destinations",
    ]);
    expect(findInconclusiveResults(results).map((result) => result.inconclusive_pages)).toEqual([
      ["24", "26"],
      ["31"],
    ]);
  });
});

describe("findCmmMappingWarning", () => {
  it("returns a failed CMM mapping check with both values", () => {
    const warning: RuleResult = {
      rule_id: "CUSTOM_CMM_MAPPING_SUSPECT",
      status: "FAIL",
      evidence: {
        page: "1",
        location: { type: "bbox", bbox: [0, 0, 0, 0] },
        observed_value: "79-30-01",
        expected_value: "79-30-02",
      },
    };

    expect(findCmmMappingWarning([
      { ...warning, rule_id: "OTHER_RULE" },
      { ...warning, status: "PASS" },
      warning,
    ])).toBe(warning);
  });

  it("ignores results without usable evidence", () => {
    expect(findCmmMappingWarning([
      {
        rule_id: "CUSTOM_CMM_MAPPING_SUSPECT",
        status: "FAIL",
        evidence: null,
      },
    ])).toBeUndefined();
  });
});