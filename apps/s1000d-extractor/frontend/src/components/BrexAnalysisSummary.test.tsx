import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { BrexProfileDetail } from "../lib/api";
import type { DmValidationViolation, WizardDm } from "../lib/wizardTypes";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      options ? `${key}:${Object.values(options).join(",")}` : key,
  }),
}));

import { BrexAnalysisSummary } from "./BrexAnalysisSummary";

const profile: BrexProfileDetail = {
  id: "brex-1",
  name: "Project rules",
  s1000d_issue: "4.2",
  dmc: "DMC-TST-A-A-00-00-00A-040A-A",
  dm_code: { modelIdentCode: "TST" },
  rules: [
    {
      rule_id: "automatic",
      object_path: "//para",
      allowed_flag: "2",
      object_use: "",
      object_values: [],
      rules_context: null,
      context_id: null,
      severity_level: null,
      supported: true,
      support_status: "automatic",
      support_reason: null,
    },
    {
      rule_id: "contextual",
      object_path: "//step",
      allowed_flag: "2",
      object_use: "",
      object_values: [],
      rules_context: "http://example.test/proced.xsd",
      context_id: null,
      severity_level: null,
      supported: true,
      support_status: "contextual",
      support_reason: null,
    },
    {
      rule_id: "unsupported",
      object_path: "//item/@kind",
      allowed_flag: "2",
      object_use: "",
      object_values: [],
      rules_context: null,
      context_id: null,
      severity_level: null,
      supported: false,
      support_status: "unsupported",
      support_reason: "unsupported_value_form",
    },
  ],
  unsupported_rules: [{
    rule_type: "nonContextRule",
    rule_id: "manual",
    description: "Manual review required.",
  }],
};

type TestDm = Pick<WizardDm, "dm_id" | "title" | "has_xml" | "brex_violations">;

const sharedWarning: DmValidationViolation = {
  severity: "warning",
  rule: "BREX_VALUE_UNSUPPORTED",
  message: "Forme ou tailoring de valeur BREX non pris en charge.",
  path: "//@infoEntityRefIdent",
  brex_rule_id: "icn-format",
};

const actualViolation: DmValidationViolation = {
  severity: "error",
  rule: "BREX",
  message: "Objet obligatoire absent.",
  path: "//required-object",
  brex_rule_id: "required-object",
};

function renderSummary(
  dms: TestDm[],
  options: { hasProfile?: boolean; profileId?: string | null } = {},
): string {
  const profileId = options.profileId === undefined ? profile.id : options.profileId;
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  if (profileId) client.setQueryData(["s1000d-brex", profileId], profile);
  return renderToStaticMarkup(
    createElement(
      QueryClientProvider,
      { client },
      createElement(BrexAnalysisSummary, {
        hasProfile: options.hasProfile ?? true,
        profileId,
        dms,
      }),
    ),
  );
}

function dm(
  id: string,
  violations: DmValidationViolation[],
  hasXml = true,
): TestDm {
  return {
    dm_id: id,
    title: `DM ${id}`,
    has_xml: hasXml,
    brex_violations: violations,
  };
}

describe("BREX analysis summary", () => {
  it("shows coverage and groups the same unsupported rule across DMs", () => {
    const markup = renderSummary([
      dm("dm-1", [sharedWarning]),
      dm("dm-2", [sharedWarning]),
    ]);

    expect(markup).toContain("migration.brex.coverageAutomatic:1");
    expect(markup).toContain("migration.brex.coverageContextual:1");
    expect(markup).toContain("migration.brex.coverageUnsupported:2");
    expect(markup).toContain("migration.generate.brexNoViolations");
    expect(markup).toContain("migration.generate.brexPartialStatus");
    expect(markup).toContain("migration.generate.brexWarningGroupCount:1");
    expect(markup).toContain("migration.generate.brexAffectedDms:2,2");
    expect(markup.split("BREX_VALUE_UNSUPPORTED").length - 1).toBe(1);
  });

  it("reports actual violations separately from global unsupported warnings", () => {
    const markup = renderSummary([
      dm("dm-1", [actualViolation, sharedWarning]),
      dm("dm-2", [sharedWarning]),
    ]);

    expect(markup).toContain("migration.generate.brexViolationsFound:1,1");
    expect(markup).toContain("migration.generate.brexPartialStatus");
    expect(markup).toContain("migration.generate.brexWarningGroupCount:1");
  });

  it("does not report a final result until every DM has generated XML", () => {
    const markup = renderSummary([
      dm("dm-1", []),
      dm("dm-2", [], false),
    ]);

    expect(markup).toContain("migration.generate.brexAnalysisPending:1,2");
    expect(markup).not.toContain("migration.generate.brexNoViolations");
  });

  it("does not show a profile result when no profile is selected", () => {
    expect(renderSummary([dm("dm-1", [])], { hasProfile: false })).toBe("");
  });
});
