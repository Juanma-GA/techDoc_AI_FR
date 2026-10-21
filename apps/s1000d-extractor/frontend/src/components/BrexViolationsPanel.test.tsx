import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { DmValidationViolation } from "../lib/wizardTypes";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      options ? `${key}:${Object.values(options).join(",")}` : key,
  }),
}));

import { BrexViolationsPanel } from "./BrexViolationsPanel";

const requiredObjectViolation: DmValidationViolation = {
  severity: "error",
  rule: "BREX",
  message: "Objet obligatoire absent.",
  path: "//required-object",
  brex_rule_id: "required-object",
};

function renderPanel(
  props: Partial<{
    hasProfile: boolean;
    isComplete: boolean;
    violations: DmValidationViolation[];
  }> = {},
): string {
  return renderToStaticMarkup(
    createElement(BrexViolationsPanel, {
      hasProfile: true,
      isComplete: true,
      violations: [],
      ...props,
    }),
  );
}

describe("BREX violations panel", () => {
  it("does not claim a result when no profile is selected or generation is incomplete", () => {
    expect(renderPanel({ hasProfile: false })).toBe("");
    expect(renderPanel({ isComplete: false })).toBe("");
  });

  it("leaves the no-violation status to the global analysis summary", () => {
    expect(renderPanel()).toBe("");
  });

  it("shows actual DM violations but leaves repeated warnings to the global summary", () => {
    const markup = renderPanel({
      violations: [
        requiredObjectViolation,
        {
          severity: "warning",
          rule: "BREX_UNSUPPORTED",
          message: "Règle non évaluée automatiquement.",
          path: "BREX/non-context",
          brex_severity_level: "warning",
        },
      ],
    });

    expect(markup).toContain("<details>");
    expect(markup).not.toContain("<details open");
    expect(markup).toContain("migration.generate.brexViolations:1");
    expect(markup).toContain(
      'class="badge warn">migration.generate.brexViolations:1</span>',
    );
    expect(markup).toContain("migration.generate.brexSeverity.error");
    expect(markup).toContain("required-object");
    expect(markup).toContain("//required-object");
    expect(markup).toContain("Objet obligatoire absent.");
    expect(markup).not.toContain("BREX_UNSUPPORTED");
    expect(markup).not.toContain("Règle non évaluée automatiquement.");
  });
});
