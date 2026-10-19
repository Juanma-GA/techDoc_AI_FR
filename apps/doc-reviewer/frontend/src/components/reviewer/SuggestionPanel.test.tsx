import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Suggestion } from "../../types/domain";

const mocks = vi.hoisted(() => ({
  useClientRules: vi.fn(),
}));

vi.mock("../../hooks/useClientConfig", () => ({
  useClientRules: mocks.useClientRules,
}));
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "fr" },
  }),
}));
vi.mock("./SuggestionItem", () => ({
  SuggestionItem: ({ suggestion }: { suggestion: Suggestion }) => (
    <div data-testid="suggestion-item" data-suggestion-id={suggestion.id} />
  ),
}));
vi.mock("../ConfirmDialog", () => ({
  ConfirmDialog: () => null,
}));

import { useFiltersStore } from "../../stores/filtersStore";
import { SuggestionPanel } from "./SuggestionPanel";

function makeSuggestion(id: string, ruleCode: string): Suggestion {
  return {
    id,
    document_id: "document",
    run_id: null,
    rule_kind: "custom",
    rule_code: ruleCode,
    source_kind: "regle",
    severity: "warning",
    message: "Test finding",
    original_text: "original",
    proposed_text: "proposed",
    page: 1,
    bbox: { x0: 0, y0: 0, x1: 1, y1: 1 },
    span_index: 0,
    target_id: null,
    status: "open",
    feedback: "",
    applied_at: null,
    applied_version: null,
    created_at: "2026-01-01T00:00:00Z",
  };
}

describe("SuggestionPanel rule order", () => {
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
    useFiltersStore.setState({
      showUnitConversions: true,
      hideAccepted: false,
      ruleCodeFilter: null,
    });
    mocks.useClientRules.mockReturnValue({
      data: [
        { code: "RULE_10", rule_number: 10 },
        { code: "RULE_2", rule_number: 2 },
      ],
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.clearAllMocks();
  });

  it("renders compact borderless group metadata and keeps the group expandable", async () => {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <SuggestionPanel
            suggestions={[
              makeSuggestion("group-first", "RULE_2"),
              makeSuggestion("group-second", "RULE_2"),
              makeSuggestion("single", "RULE_10"),
            ]}
            selectedId={null}
            onSelect={() => undefined}
            onAccept={() => undefined}
            onReject={() => undefined}
            onRejectAll={() => undefined}
            onSaveEdit={() => undefined}
            onSaveFeedback={() => undefined}
            onUnreject={() => undefined}
            onUndo={() => undefined}
          />
        </MemoryRouter>,
      );
    });

    const head = container.querySelector(".suggestion-bucket-head")!;
    const toggle = head.querySelector<HTMLButtonElement>(".suggestion-bucket-toggle")!;
    const reject = head.querySelector<HTMLButtonElement>(".suggestion-bucket-reject")!;
    expect(head.querySelector(".badge")).toBeNull();
    expect(head.querySelector(".suggestion-bucket-rule-number")?.textContent).toBe("#2");
    expect(reject.getAttribute("aria-label")).toBe("reviewer.suggestion.rejectAll");
    expect(reject.getAttribute("title")).toBe("reviewer.suggestion.rejectAll");
    expect(reject.textContent).toBe("");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");

    act(() => toggle.click());

    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(container.querySelectorAll('[data-testid="suggestion-item"]')).toHaveLength(3);
  });

  it("scrolls to each new selection within an expanded group without scrolling on manual collapse", async () => {
    const scrolledIds: string[] = [];
    const previousScrollIntoView = HTMLElement.prototype.scrollIntoView;
    HTMLElement.prototype.scrollIntoView = vi.fn(function (this: HTMLElement) {
      scrolledIds.push(this.dataset.suggestionId ?? "");
    });
    const suggestions = [
      makeSuggestion("group-first", "RULE_2"),
      makeSuggestion("group-second", "RULE_2"),
    ];
    const renderSelection = async (selectedId: string, focusRequest = 0) => {
      await act(async () => {
        root.render(
          <MemoryRouter>
            <SuggestionPanel
              suggestions={suggestions}
              selectedId={selectedId}
              focusRequest={focusRequest}
              onSelect={() => undefined}
              onAccept={() => undefined}
              onReject={() => undefined}
              onRejectAll={() => undefined}
              onSaveEdit={() => undefined}
              onSaveFeedback={() => undefined}
              onUnreject={() => undefined}
              onUndo={() => undefined}
            />
          </MemoryRouter>,
        );
      });
    };

    try {
      await renderSelection("group-first");
      expect(scrolledIds).toEqual(["group-first"]);
      expect(container.querySelector(".suggestion-bucket.expanded")).not.toBeNull();

      await renderSelection("group-second");
      expect(scrolledIds).toEqual(["group-first", "group-second"]);

      const toggle = container.querySelector<HTMLButtonElement>(".suggestion-bucket-toggle")!;
      act(() => toggle.click());
      expect(toggle.getAttribute("aria-expanded")).toBe("false");
      expect(scrolledIds).toHaveLength(2);

      await renderSelection("group-second", 1);
      expect(toggle.getAttribute("aria-expanded")).toBe("true");
      expect(scrolledIds).toEqual(["group-first", "group-second", "group-second"]);

      await renderSelection("group-second", 2);
      expect(scrolledIds).toEqual([
        "group-first", "group-second", "group-second", "group-second",
      ]);
    } finally {
      HTMLElement.prototype.scrollIntoView = previousScrollIntoView;
    }
  });

  it("orders numbered groups numerically and keeps unnumbered groups last in their original order", async () => {
    await act(async () => {
      root.render(
        <SuggestionPanel
          suggestions={[
            makeSuggestion("unknown-first", "UNKNOWN_A"),
            makeSuggestion("ten", "RULE_10"),
            makeSuggestion("unknown-second", "UNKNOWN_B"),
            makeSuggestion("two", "RULE_2"),
          ]}
          selectedId={null}
          onSelect={() => undefined}
          onAccept={() => undefined}
          onReject={() => undefined}
          onRejectAll={() => undefined}
          onSaveEdit={() => undefined}
          onSaveFeedback={() => undefined}
          onUnreject={() => undefined}
          onUndo={() => undefined}
        />,
      );
    });

    const renderedIds = Array.from(
      container.querySelectorAll<HTMLElement>('[data-testid="suggestion-item"]'),
      (item) => item.dataset.suggestionId,
    );

    expect(renderedIds).toEqual(["two", "ten", "unknown-first", "unknown-second"]);
  });
});
