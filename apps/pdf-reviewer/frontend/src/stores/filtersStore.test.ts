import { beforeEach, describe, expect, it } from "vitest";

import { useFiltersStore } from "./filtersStore";

describe("filtersStore — standard selection", () => {
  beforeEach(() => {
    useFiltersStore.setState({ lastStandardId: null, lastStandardVersionId: null });
  });

  it("persists the last (standard, version) chosen at upload", () => {
    useFiltersStore.getState().setLastStandard("std-abc", "ver-1");
    expect(useFiltersStore.getState().lastStandardId).toBe("std-abc");
    expect(useFiltersStore.getState().lastStandardVersionId).toBe("ver-1");
  });

  it("clears both ids when picking transverse", () => {
    useFiltersStore.getState().setLastStandard("std-abc", "ver-1");
    useFiltersStore.getState().setLastStandard(null, null);
    expect(useFiltersStore.getState().lastStandardId).toBeNull();
    expect(useFiltersStore.getState().lastStandardVersionId).toBeNull();
  });
});
