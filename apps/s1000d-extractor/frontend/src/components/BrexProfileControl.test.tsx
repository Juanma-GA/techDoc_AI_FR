import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { BrexProfile, BrexProfileDetail } from "../lib/api";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      options ? `${key}:${Object.values(options).join(",")}` : key,
  }),
}));

import { BrexProfileControl } from "./BrexProfileControl";

const profile: BrexProfile = {
  id: "brex-1",
  name: "Project rules",
  s1000d_issue: "4.2",
};

const detail: BrexProfileDetail = {
  ...profile,
  dmc: "DMC-TST-A-A-00-00-00A-040A-A",
  dm_code: { modelIdentCode: "TST" },
  rules: [{
    rule_id: "no-emphasis",
    object_path: "//emphasis",
    allowed_flag: "0",
    object_use: "Emphasis is not allowed.",
    object_values: [{
      value_allowed: "approved",
      value_text: "approved",
      value_form: null,
      value_tailoring: "closed",
    }],
    rules_context: null,
    context_id: null,
    severity_level: null,
    supported: true,
  }],
  unsupported_rules: [],
};

function renderControl(issue: "4.1" | "4.2" = "4.2") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(["s1000d-brex"], [profile]);
  client.setQueryData(["s1000d-brex", profile.id], detail);
  return renderToStaticMarkup(
    createElement(
      QueryClientProvider,
      { client },
      createElement(BrexProfileControl, {
        issue,
        value: profile.id,
        onChange: vi.fn(),
        onReadyChange: vi.fn(),
      }),
    ),
  );
}

describe("BREX profile control", () => {
  it("offers profile upload before selecting an existing profile", () => {
    const markup = renderControl();

    expect(markup.indexOf("migration.brex.addProfileTitle")).toBeLessThan(
      markup.indexOf("migration.upload.brex"),
    );
    expect(markup.indexOf("migration.brex.file")).toBeLessThan(
      markup.indexOf("migration.upload.brex"),
    );
    expect(markup.indexOf("migration.brex.profileName")).toBeLessThan(
      markup.indexOf("migration.upload.brex"),
    );
  });

  it("shows rule details inside a collapsed native disclosure", () => {
    const markup = renderControl();

    expect(markup).toContain("<details>");
    expect(markup).not.toContain("<details open");
    expect(markup).toContain("migration.brex.rulesSummary:1");
    expect(markup).toContain("//emphasis");
    expect(markup).toContain("approved");
  });

  it("warns when a selected BREX Issue differs from the target DM Issue", () => {
    const markup = renderControl("4.1");

    expect(markup).toContain("migration.brex.issueMismatch:4.2,4.1");
  });
});
