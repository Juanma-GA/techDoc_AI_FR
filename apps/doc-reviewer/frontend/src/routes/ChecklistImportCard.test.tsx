import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import i18n from "../i18n";
import type { CompiledRuleSummary } from "../hooks/useRules";
import { CompiledRuleRows } from "./ChecklistImportCard";


describe("CompiledRuleRows", () => {
  it("keeps each imported checklist line in its compiled status", async () => {
    await i18n.changeLanguage("en");
    const base = {
      active: false,
      source: "user_checklist" as const,
      origin_ref: "checklist.xlsx:Review:2",
      manual_instruction: null,
      compilation_error: null,
    };
    const rules: CompiledRuleSummary[] = [
      { ...base, id: "R1", topic: "Revision", execution: "deterministic", active: true },
      { ...base, id: "R2", topic: "Logo", execution: "manual", manual_instruction: "Inspect logo" },
      { ...base, id: "R3", topic: "Table", execution: "unsupported", compilation_error: "count_equals unsupported" },
    ];

    const markup = renderToStaticMarkup(<table><tbody><CompiledRuleRows rules={rules} /></tbody></table>);

    expect(markup).toContain('data-execution="deterministic"');
    expect(markup).toContain("Active immediately");
    expect(markup).toContain('data-execution="manual"');
    expect(markup).toContain("Inspect logo");
    expect(markup).toContain('data-execution="unsupported"');
    expect(markup).toContain("count_equals unsupported");
  });
});