// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { brexApi } from "../lib/api";
import { BrexProfileDeleteAction } from "./BrexProfileDeleteAction";

vi.mock("../lib/api", () => ({
  brexApi: { delete: vi.fn() },
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

let root: Root | undefined;
let container: HTMLDivElement | undefined;

beforeEach(() => {
  Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", {
    value: true,
    configurable: true,
  });
});

afterEach(() => {
  if (root) act(() => root?.unmount());
  container?.remove();
  root = undefined;
  container = undefined;
  vi.clearAllMocks();
});

describe("BREX profile delete action", () => {
  it("requires a second click before deleting and updates the profile cache", async () => {
    const client = new QueryClient();
    const onDeleted = vi.fn();
    client.setQueryData(["s1000d-brex"], [{ id: "brex-1", name: "Project rules" }]);
    vi.mocked(brexApi.delete).mockResolvedValue({ id: "brex-1", status: "deleted" });
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(
        createElement(
          QueryClientProvider,
          { client },
          createElement(BrexProfileDeleteAction, {
            profileId: "brex-1",
            disabled: false,
            onDeleted,
          }),
        ),
      );
    });

    const button = container.querySelector("button");
    expect(button?.textContent).toBe("migration.docs.delete");
    await act(async () => {
      button?.click();
    });
    expect(button?.textContent).toBe("common.confirmAgain");
    expect(brexApi.delete).not.toHaveBeenCalled();

    await act(async () => {
      button?.click();
    });
    expect(brexApi.delete).toHaveBeenCalledWith("brex-1", expect.any(String));
    expect(onDeleted).toHaveBeenCalledWith("brex-1");
    expect(client.getQueryData(["s1000d-brex"])).toEqual([]);
  });
});
