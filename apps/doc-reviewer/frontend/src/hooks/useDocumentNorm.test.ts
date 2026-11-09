import { describe, expect, it } from "vitest";

import type { ClientRule } from "./useClientConfig";
import { activeRuleCounts, normNeedsChoice, type DocumentNorm } from "./useDocumentNorm";

function rule(code: string, bundle: string, active: boolean, scope: ClientRule["scope"] = "verification"): ClientRule {
  return {
    code,
    bundle_code: bundle,
    bundle_label: bundle,
    name: code,
    description: code,
    message: code,
    rule_number: 1,
    kind: "content",
    scope,
    severity: "warning",
    execution: "deterministic",
    active,
    catalog_code: "CATALOG",
    catalog_version: "v1",
    translations: {},
  };
}

const norms = [
  { code: "ata100", label: "ATA100" },
  { code: "s1000d", label: "S1000D" },
];

const detection = (detected: string | null): DocumentNorm => ({
  detected_norm: detected,
  default_norm: "ata100",
  norms,
  page_revision_tracking: detected !== "s1000d",
});

describe("document norm choice", () => {
  it("counts the active verification rules of each norm", () => {
    const rules = [
      rule("A1", "ata100", true),
      rule("A2", "ata100", false),
      rule("A3", "ata100", true, "preparation"),
      rule("S1", "s1000d", false),
      rule("T1", "ste100_rules", true),
    ];

    expect(activeRuleCounts(rules, norms)).toEqual({ ata100: 1, s1000d: 0 });
  });

  it("asks only when the detected norm has no active rule", () => {
    const onlyAta = [rule("A1", "ata100", true), rule("S1", "s1000d", false)];
    const both = [rule("A1", "ata100", true), rule("S1", "s1000d", true)];
    const onlyS1000d = [rule("A1", "ata100", false), rule("S1", "s1000d", true)];

    expect(normNeedsChoice(detection("s1000d"), onlyAta)).toBe(true);
    expect(normNeedsChoice(detection("s1000d"), both)).toBe(false);
    expect(normNeedsChoice(detection("s1000d"), onlyS1000d)).toBe(false);
    expect(normNeedsChoice(detection("ata100"), onlyS1000d)).toBe(true);
  });

  it("does not ask without detection, rules or several norms", () => {
    const rules = [rule("A1", "ata100", false)];

    expect(normNeedsChoice(undefined, rules)).toBe(false);
    expect(normNeedsChoice(detection(null), rules)).toBe(false);
    expect(normNeedsChoice(detection("ata100"), undefined)).toBe(false);
    expect(
      normNeedsChoice({ ...detection("ata100"), norms: norms.slice(0, 1) }, rules),
    ).toBe(false);
  });
});
