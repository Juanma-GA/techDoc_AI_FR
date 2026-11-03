// @vitest-environment jsdom

import { act, createElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { preliminaryApi } from "./preliminaryApi";
import type { PreliminaryState } from "./preliminaryTypes";
import { preliminaryRulesQueryKey } from "./preliminaryRules";
import { usePreliminaryReview } from "./usePreliminaryReview";

vi.mock("./preliminaryApi", () => ({
  preliminaryApi: { save: vi.fn(), read: vi.fn() },
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: { defaultValue?: string }) => options?.defaultValue ?? key,
  }),
}));

const initial: PreliminaryState = {
  revision: 1, active_dm_id: "proc", source_format: "docx", source_changed: false,
  reviews: { proc: {
    fingerprint: "synthetic", rules_revision: 0, status: "pending", passages: [],
    position: { page: 1, scroll_top: 0, selected_id: null }, saved_at: null,
  } },
};

let root: Root;
let container: HTMLDivElement;
let current: ReturnType<typeof usePreliminaryReview>;
let client: QueryClient;

function Probe() {
  current = usePreliminaryReview("synthetic-document", initial);
  return null;
}

beforeEach(() => {
  Object.defineProperty(globalThis, "IS_REACT_ACT_ENVIRONMENT", { value: true, configurable: true });
  vi.useFakeTimers();
  vi.mocked(preliminaryApi.save).mockImplementation(async (_doc, revision) => ({
    ...initial, revision: revision + 1,
  }));
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  act(() => root.render(createElement(QueryClientProvider, { client }, createElement(Probe))));
});

afterEach(async () => {
  await act(async () => { root.unmount(); });
  container.remove();
  client.clear();
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe("server-persisted procedural review", () => {
  it("marks the still-open review stale after saving settings without deleting local edits", async () => {
    act(() => current.edit({ dm_id: "proc", op: "decide", passage_id: "p", text: "Local correction" }));
    await act(async () => {
      client.setQueryData(preliminaryRulesQueryKey, { revision: 1, groups: [] });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(current.state.source_changed).toBe(true);
    expect(current.state.reviews.proc?.status).toBe("stale");
    expect(current.edits.p).toBe("Local correction");
    expect(preliminaryApi.save).not.toHaveBeenCalled();
  });

  it("does not invalidate a newer review using an older settings cache", async () => {
    vi.mocked(preliminaryApi.save).mockResolvedValueOnce({
      ...initial, reviews: { proc: { ...initial.reviews.proc!, rules_revision: 2 } },
    });
    await act(async () => {
      await current.act({ dm_id: "proc", op: "restart" });
      client.setQueryData(preliminaryRulesQueryKey, { revision: 1, groups: [] });
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(current.state.reviews.proc?.status).toBe("pending");
    expect(current.state.source_changed).toBe(false);
  });

  it("flushes the last scroll position before a classification and serializes revisions", async () => {
    act(() => current.position("proc", { page: 2, scroll_top: 420.5, selected_id: "passage" }));
    expect(current.dirty).toBe(false);
    await act(async () => {
      expect(await current.act({
        dm_id: "proc", op: "decide", passage_id: "passage", destination: "safety",
      })).toBe(true);
    });
    expect(preliminaryApi.save).toHaveBeenNthCalledWith(1, "synthetic-document", 1, {
      dm_id: "proc", op: "cursor", page: 2, scroll_top: 420.5, selected_id: "passage",
    }, false);
    expect(preliminaryApi.save).toHaveBeenNthCalledWith(2, "synthetic-document", 2, {
      dm_id: "proc", op: "decide", passage_id: "passage", destination: "safety",
    }, false);
    expect(current.state.revision).toBe(3);
    expect(current.dirty).toBe(false);
    expect(current.error).toBeNull();
  });

  it("keeps controls active while saving reader position in the background", async () => {
    let acknowledge: (state: PreliminaryState) => void = () => {};
    vi.mocked(preliminaryApi.save).mockImplementationOnce(() => new Promise((resolve) => {
      acknowledge = resolve;
    }));
    act(() => current.position("proc", { page: 2, scroll_top: 420, selected_id: "passage" }));
    expect(current.dirty).toBe(false);
    await act(async () => { await vi.advanceTimersByTimeAsync(300); });
    expect(current.saving).toBe(false);
    await act(async () => { acknowledge({ ...initial, revision: 2 }); });
    expect(current.dirty).toBe(false);
  });

  it("does not claim a failed action was saved and blocks navigation until retry", async () => {
    vi.mocked(preliminaryApi.save).mockRejectedValueOnce(new Error("Synthetic save failure"));
    await act(async () => {
      expect(await current.act({ dm_id: "proc", op: "complete", confirm_empty: true })).toBe(false);
    });
    expect(current.error).toBe("Synthetic save failure");
    expect(current.state.revision).toBe(1);
    await act(async () => { expect(await current.flush()).toBe(false); });
    await act(async () => { expect(await current.retry()).toBe(true); });
    expect(current.error).toBeNull();
    expect(current.state.revision).toBe(2);
  });

  it("debounces text-only corrections without overwriting a classification", async () => {
    act(() => {
      current.edit({ dm_id: "proc", op: "decide", passage_id: "p", text: "First" });
      current.edit({ dm_id: "proc", op: "decide", passage_id: "p", text: "Final" });
    });
    expect(current.edits.p).toBe("Final");
    await act(async () => { await vi.advanceTimersByTimeAsync(500); });
    expect(preliminaryApi.save).toHaveBeenCalledTimes(1);
    expect(preliminaryApi.save).toHaveBeenCalledWith("synthetic-document", 1, {
      dm_id: "proc", op: "decide", passage_id: "p", text: "Final",
    }, false);
    expect(current.edits).toEqual({});
    expect(current.dirty).toBe(false);
  });

  it("flushes pending reader position on unmount with keepalive", async () => {
    act(() => current.position("proc", { page: 3, scroll_top: 820, selected_id: null }));
    await act(async () => { root.unmount(); });
    expect(preliminaryApi.save).toHaveBeenCalledWith("synthetic-document", 1, {
      dm_id: "proc", op: "cursor", page: 3, scroll_top: 820, selected_id: null,
    }, true);
  });

  it("retains a newer edit while an earlier save is in flight", async () => {
    let acknowledge: (state: PreliminaryState) => void = () => {};
    vi.mocked(preliminaryApi.save).mockImplementationOnce(() => new Promise((resolve) => {
      acknowledge = resolve;
    }));
    act(() => current.edit({ dm_id: "proc", op: "decide", passage_id: "p", text: "First" }));
    await act(async () => { await vi.advanceTimersByTimeAsync(500); });
    act(() => current.edit({ dm_id: "proc", op: "decide", passage_id: "p", text: "Newer" }));
    await act(async () => { acknowledge({ ...initial, revision: 2 }); });
    expect(current.edits.p).toBe("Newer");
    await act(async () => { await vi.advanceTimersByTimeAsync(500); });
    expect(preliminaryApi.save).toHaveBeenLastCalledWith("synthetic-document", 2, {
      dm_id: "proc", op: "decide", passage_id: "p", text: "Newer",
    }, false);
    expect(current.edits).toEqual({});
  });
});
