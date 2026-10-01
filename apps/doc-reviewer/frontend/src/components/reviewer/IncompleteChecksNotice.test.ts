import { describe, expect, it } from "vitest";

import { findInconclusiveResults } from "./IncompleteChecksNotice";
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
      { rule_id: "RULE_FAIL", rule_title: "Failed check", status: "FAIL", evidence: null },
    ];

    expect(findInconclusiveResults(results).map((result) => result.rule_title)).toEqual([
      "Revision date",
    ]);
    expect(findInconclusiveResults(results)[0]?.inconclusive_pages).toEqual(["24", "26"]);
  });
});