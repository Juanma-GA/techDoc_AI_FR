import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useQueuedSave } from "./useQueuedSave";

afterEach(cleanup);

describe("ordered local autosaves", () => {
  it("serializes requests and coalesces pending edits without losing the last state", async () => {
    let resolveFirst: () => void = () => {};
    const first = new Promise<void>((resolve) => { resolveFirst = resolve; });
    const save = vi.fn<(value: number) => Promise<void>>()
      .mockImplementationOnce(() => first).mockResolvedValue(undefined);
    const { result, rerender } = renderHook(({ value }) => useQueuedSave(value, save), {
      initialProps: { value: 1 },
    });
    rerender({ value: 2 });
    rerender({ value: 3 });
    expect(save).toHaveBeenCalledTimes(1);
    await act(async () => { resolveFirst(); await result.current.flush(); });
    expect(save.mock.calls.map(([value]) => value)).toEqual([1, 3]);
    expect(result.current.error).toBeNull();
    expect(result.current.saving).toBe(false);
  });

  it("surfaces a failed save and retries the retained snapshot", async () => {
    const save = vi.fn<(value: number) => Promise<void>>()
      .mockRejectedValueOnce(new Error("Disk full")).mockResolvedValue(undefined);
    const { result } = renderHook(() => useQueuedSave(7, save));
    await waitFor(() => expect(result.current.error).toBeInstanceOf(Error));
    await act(async () => { await result.current.flush(); });
    expect(save.mock.calls.map(([value]) => value)).toEqual([7, 7]);
    expect(result.current.error).toBeNull();
    expect(result.current.saved).toBe(1);
  });
});
