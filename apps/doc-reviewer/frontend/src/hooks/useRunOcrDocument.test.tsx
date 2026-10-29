import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock("../lib/api", () => ({
  api: { post: mocks.post, get: vi.fn(), patch: vi.fn() },
}));

import { useRunOcrDocument } from "./usePreparation";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

type Hook = ReturnType<typeof useRunOcrDocument>;

describe("useRunOcrDocument", () => {
  let container: HTMLDivElement;
  let root: Root;
  let hook: Hook;
  const seen: string[] = [];

  function Probe() {
    hook = useRunOcrDocument("doc-1");
    if (hook.isPending && hook.progress) {
      seen.push(`${hook.progress.done}/${hook.progress.total}`);
    }
    return null;
  }

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    mocks.post.mockReset();
    seen.length = 0;
    act(() => {
      root.render(
        <QueryClientProvider client={new QueryClient()}>
          <Probe />
        </QueryClientProvider>,
      );
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("runs the pending pages one by one and reports done over total", async () => {
    mocks.post.mockResolvedValue({});

    await act(async () => {
      hook.mutate([2, 5, 7]);
    });

    expect(mocks.post.mock.calls.map((call) => call[0])).toEqual([
      "/documents/doc-1/preparation/ocr/pages/2",
      "/documents/doc-1/preparation/ocr/pages/5",
      "/documents/doc-1/preparation/ocr/pages/7",
    ]);
    expect(seen.length).toBeGreaterThan(0);
    expect(hook.progress).toEqual({ done: 3, total: 3 });
  });

  it("stops at the first failing page and keeps the count of finished pages", async () => {
    mocks.post.mockResolvedValueOnce({}).mockRejectedValueOnce(new Error("OCR down"));

    await act(async () => {
      hook.mutate([1, 2, 3]);
    });

    expect(mocks.post).toHaveBeenCalledTimes(2);
    expect(hook.isError).toBe(true);
    expect(hook.progress).toEqual({ done: 1, total: 3 });
  });
});
