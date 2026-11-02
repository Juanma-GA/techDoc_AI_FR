import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ClientRule } from "../hooks/useClientConfig";
import { ClientRuleBundles } from "./ClientRuleBundles";
import { ClientRules } from "./ClientRules";

const mockClientHooks = vi.hoisted(() => ({
  useClientConfig: vi.fn(),
  useClientPreparationPageTitles: vi.fn(),
  useClientRules: vi.fn(),
  usePatchClientRule: vi.fn(),
  usePatchClientRuleBundle: vi.fn(),
  useSaveClientPreparationPageTitles: vi.fn(),
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
    scope: "verification",
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
    scope: "verification",
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
    mockClientHooks.useClientPreparationPageTitles.mockReturnValue({
      isLoading: false,
      isError: false,
      data: { titles: ["INTRODUCTION"] },
      refetch: vi.fn(),
    });
    mockClientHooks.useSaveClientPreparationPageTitles.mockReturnValue({
      isError: false,
      isPending: false,
      mutate: vi.fn(),
    });
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
    expect([...panels].every((panel) => !panel.open)).toBe(true);
    const firstPanel = panels.item(0);

    await act(async () => {
      firstPanel.open = true;
      firstPanel.dispatchEvent(new Event("toggle"));
    });

    const updatedPanels = container.querySelectorAll<HTMLDetailsElement>("details.collapsible");
    expect(updatedPanels.item(0).open).toBe(true);
    expect(updatedPanels.item(1).open).toBe(false);
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

  it("shows the ATA100 and S1000D norms of one client as separate groups with their own bulk toggle", async () => {
    const [base] = rules;
    if (!base) throw new Error("Expected a base test rule");
    const ataRule: ClientRule = { ...base, code: "ATA_RULE", bundle_code: "ata100", bundle_label: "ATA100" };
    const s1000dRule: ClientRule = {
      ...base,
      code: "S1000D_RULE",
      bundle_code: "s1000d",
      bundle_label: "S1000D",
      catalog_code: "THALES-S1000D",
      active: false,
    };
    const onToggleBundle = vi.fn();
    await act(async () => {
      root.render(
        <ClientRuleBundles
          rules={[ataRule, s1000dRule]}
          allRules={[ataRule, s1000dRule]}
          targetRuleCode={null}
          localizeRule={(rule, field) => rule[field]}
          bulkUpdatePending={false}
          ruleUpdatePending={false}
          onToggleRule={vi.fn()}
          onToggleBundle={onToggleBundle}
        />,
      );
    });

    const panels = container.querySelectorAll<HTMLDetailsElement>("details.collapsible");
    expect([...panels].map((panel) => panel.querySelector("strong")?.textContent)).toEqual([
      "ATA100",
      "S1000D",
    ]);
    const labels = [...container.querySelectorAll("button")].map((button) =>
      button.getAttribute("aria-label"),
    );
    expect(labels).toEqual([
      "rules.client.disableAll ATA100",
      "rules.client.enableAll S1000D",
    ]);

    const s1000dButton = [...container.querySelectorAll("button")].find((button) =>
      button.getAttribute("aria-label")?.endsWith("S1000D"),
    );
    await act(async () => s1000dButton?.click());

    expect(onToggleBundle).toHaveBeenCalledTimes(1);
    expect(onToggleBundle).toHaveBeenCalledWith([s1000dRule], true);
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
        client_code: "THALES",
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
      data: [
        rules[0],
        {
          ...rules[0],
          code: "PREPARATION_RULE",
          name: "Preparation rule",
          scope: "preparation",
        },
      ],
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
    expect(container.textContent).toContain("THALES_RULE");
    expect(container.textContent).not.toContain("PREPARATION_RULE");

    const preparationButton = [...container.querySelectorAll<HTMLButtonElement>('[role="group"] button')]
      .find((button) => button.textContent?.includes("rules.client.scope.preparation"));
    expect(preparationButton).toBeDefined();
    await act(async () => preparationButton?.click());

    expect(container.textContent).toContain("PREPARATION_RULE");
    expect(container.textContent).not.toContain("THALES_RULE");
  });

  it("adds a configured preparation title from the dedicated tab", async () => {
    const saveTitles = vi.fn();
    mockClientHooks.useClientConfig.mockReturnValue({
      isLoading: false,
      isError: false,
      data: {
        client_code: "THALES",
        label: "THALES",
        bundle: "thales_rules",
        bundle_version: "1",
        contract_version: "1",
        manifest_hash: "manifest-hash",
        mapping_hash: "mapping-hash",
        bundle_hash: "bundle-hash",
        catalogs: [],
        mapping: { fields: {}, entities: {}, tokens: {} },
        ui_options: {},
      },
      refetch: vi.fn(),
    });
    mockClientHooks.useClientRules.mockReturnValue({
      isLoading: false,
      isError: false,
      data: [],
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
    mockClientHooks.useSaveClientPreparationPageTitles.mockReturnValue({
      isError: false,
      isPending: false,
      mutate: saveTitles,
    });

    await act(async () => {
      root.render(
        <MemoryRouter>
          <ClientRules />
        </MemoryRouter>,
      );
    });

    const titlesTab = [...container.querySelectorAll<HTMLButtonElement>('[role="group"] button')]
      .find((button) => button.textContent?.includes("rules.client.pageTitles.tab"));
    expect(titlesTab).toBeDefined();
    await act(async () => titlesTab?.click());
    expect(container.textContent).toContain("INTRODUCTION");

    const input = container.querySelector<HTMLInputElement>(
      'input[aria-label="rules.client.pageTitles.inputLabel"]',
    );
    expect(input).not.toBeNull();
    await act(async () => {
      if (!input) throw new Error("Expected title input");
      const setValue = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )?.set;
      setValue?.call(input, "CUSTOM PROCEDURE");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const form = input?.closest("form");
    await act(async () => {
      form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });

    expect(saveTitles.mock.calls[0]?.[0]).toEqual(["INTRODUCTION", "CUSTOM PROCEDURE"]);
    expect(saveTitles.mock.calls[0]?.[1]).toEqual({
      onSuccess: expect.any(Function),
    });
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
      scope: "verification",
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
