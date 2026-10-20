import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ClientRule } from "../hooks/useClientConfig";
import { ClientRuleBundles } from "./ClientRuleBundles";
import { ClientRules } from "./ClientRules";

const mockClientHooks = vi.hoisted(() => ({
  useClientConfig: vi.fn(),
  useClientRules: vi.fn(),
  usePatchClientRule: vi.fn(),
  usePatchClientRuleBundle: vi.fn(),
}));

vi.mock("../hooks/useClientConfig", () => mockClientHooks);
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: "en" } }),
}));
vi.mock("../lib/suggestionText", () => ({
  localizedRuleCode: (code: string) => code,
}));

const rules: ClientRule[] = [
  {
    code: "THALES_RULE",
    bundle_code: "thales_rules",
    bundle_label: "THALES",
    name: "Thales rule",
    description: "Thales description",
    message: "Thales message",
    rule_number: 1,
    kind: "content",
    severity: "warning",
    execution: "deterministic",
    active: true,
    catalog_code: "THALES-CUSTOM",
    catalog_version: "v1",
    translations: {},
  },
  {
    code: "STE_RULE",
    bundle_code: "ste100_rules",
    bundle_label: "ASD-STE100",
    name: "STE rule",
    description: "STE description",
    message: "STE message",
    rule_number: 2,
    kind: "regex_flag",
    severity: "info",
    execution: "deterministic",
    active: true,
    catalog_code: "ASD-STE100",
    catalog_version: "issue 7",
    translations: {},
  },
];

describe("ClientRuleBundles", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", {
      value: true,
      configurable: true,
    });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("groups rules by bundle and allows each bundle section to collapse independently", async () => {
    await act(async () => {
      root.render(
        <ClientRuleBundles
          rules={rules}
          allRules={rules}
          targetRuleCode={null}
          localizeRule={(rule, field) => rule[field]}
          bulkUpdatePending={false}
          ruleUpdatePending={false}
          onToggleRule={vi.fn()}
          onToggleBundle={vi.fn()}
        />,
      );
    });

    const panels = container.querySelectorAll<HTMLDetailsElement>("details.collapsible");
    expect(panels).toHaveLength(2);
    expect(
      [...panels].every(
        (panel) =>
          panel.parentElement?.style.width === "100%" &&
          panel.parentElement.style.flexWrap === "nowrap" &&
          panel.parentElement.querySelector("button")?.style.width === "140px",
      ),
    ).toBe(true);
    expect([...panels].map((panel) => panel.querySelector("strong")?.textContent)).toEqual([
      "THALES",
      "ASD-STE100",
    ]);
    expect([...panels].every((panel) => panel.open)).toBe(true);
    const firstPanel = panels.item(0);

    await act(async () => {
      firstPanel.open = false;
      firstPanel.dispatchEvent(new Event("toggle"));
    });

    const updatedPanels = container.querySelectorAll<HTMLDetailsElement>("details.collapsible");
    expect(updatedPanels.item(0).open).toBe(false);
    expect(updatedPanels.item(1).open).toBe(true);
  });

  it("bulk toggles every rule in the bundle, including rules hidden by search", async () => {
    const thalesRule = rules[0];
    if (!thalesRule) throw new Error("Expected a Thales test rule");
    const hiddenThalesRule = { ...thalesRule, code: "HIDDEN_THALES_RULE", active: true };
    const onToggleBundle = vi.fn();
    await act(async () => {
      root.render(
        <ClientRuleBundles
          rules={[thalesRule]}
          allRules={[thalesRule, hiddenThalesRule, ...rules.slice(1)]}
          targetRuleCode={null}
          localizeRule={(rule, field) => rule[field]}
          bulkUpdatePending={false}
          ruleUpdatePending={false}
          onToggleRule={vi.fn()}
          onToggleBundle={onToggleBundle}
        />,
      );
    });

    const bulkButton = [...container.querySelectorAll("button")].find((button) =>
      button.textContent?.includes("rules.client.disableAll"),
    );
    expect(bulkButton).toBeDefined();
    await act(async () => bulkButton?.click());

    expect(onToggleBundle).toHaveBeenCalledWith([thalesRule, hiddenThalesRule], false);
  });

  it("keeps a stable hook order when client data finishes loading", async () => {
    mockClientHooks.useClientConfig.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      refetch: vi.fn(),
    });
    mockClientHooks.useClientRules.mockReturnValue({
      isLoading: true,
      isError: false,
      data: undefined,
      refetch: vi.fn(),
    });
    mockClientHooks.usePatchClientRule.mockReturnValue({
      isError: false,
      mutate: vi.fn(),
    });
    mockClientHooks.usePatchClientRuleBundle.mockReturnValue({
      isError: false,
      isPending: false,
      mutate: vi.fn(),
    });

    await act(async () => {
      root.render(
        <MemoryRouter>
          <ClientRules />
        </MemoryRouter>,
      );
    });
    expect(container.textContent).toContain("common.loading");

    mockClientHooks.useClientConfig.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        client_code: "thales",
        label: "THALES",
        bundle: "thales_rules",
        bundle_version: "1",
        contract_version: "1",
        manifest_hash: "manifest-hash",
        mapping_hash: "mapping-hash",
        bundle_hash: "bundle-hash",
        catalogs: [{ code: "THALES-CUSTOM", version: "v1", standard_version_id: "thales-v1" }],
        mapping: { fields: {}, entities: {}, tokens: {} },
        ui_options: {},
      },
      refetch: vi.fn(),
    });
    mockClientHooks.useClientRules.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [rules[0]],
      refetch: vi.fn(),
    });

    await act(async () => {
      root.render(
        <MemoryRouter>
          <ClientRules />
        </MemoryRouter>,
      );
    });
    expect(container.textContent).toContain("THALES");
  });

  it("renders the demo bundle label without exposing the normal client name", async () => {
    const demoRule: ClientRule = {
      code: "CUSTOM_TP1_DEMO_ADDRESS",
      bundle_code: "demo_rules",
      bundle_label: "DEMO",
      name: "Adresse DEMO exacte sur les pages TP1",
      description: "Adresse DEMO de reference.",
      message: "Adresse DEMO absente.",
      rule_number: 1,
      kind: "field_required",
      severity: "warning",
      execution: "deterministic",
      active: true,
      catalog_code: "DEMO-CUSTOM",
      catalog_version: "v1",
      translations: {},
    };
    mockClientHooks.useClientConfig.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        client_code: "DEMO",
        label: "DEMO",
        bundle: "demo_rules",
        bundle_version: "1.0.0",
        contract_version: "1",
        manifest_hash: "demo-manifest",
        mapping_hash: "demo-mapping",
        bundle_hash: "demo-bundle",
        catalogs: [{ code: "DEMO-CUSTOM", version: "v1", standard_version_id: "demo-v1" }],
        mapping: { fields: {}, entities: {}, tokens: {} },
        ui_options: {},
      },
      refetch: vi.fn(),
    });
    mockClientHooks.useClientRules.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [demoRule],
      refetch: vi.fn(),
    });
    mockClientHooks.usePatchClientRule.mockReturnValue({
      isError: false,
      isPending: false,
      mutate: vi.fn(),
    });
    mockClientHooks.usePatchClientRuleBundle.mockReturnValue({
      isError: false,
      isPending: false,
      mutate: vi.fn(),
    });

    await act(async () => {
      root.render(
        <MemoryRouter>
          <ClientRules />
        </MemoryRouter>,
      );
    });

    expect(container.textContent).toContain("DEMO");
    expect(container.textContent).not.toMatch(/thales/i);
  });
});
