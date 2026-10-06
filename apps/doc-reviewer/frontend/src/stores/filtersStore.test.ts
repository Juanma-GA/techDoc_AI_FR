import { beforeEach, describe, expect, it } from "vitest";

import { useFiltersStore } from "./filtersStore";

describe("filtersStore — standard selection", () => {
  beforeEach(() => {
    localStorage.removeItem("doc-reviewer-filters");
    useFiltersStore.setState({
      lastStandardId: null,
      lastStandardVersionId: null,
      activeStandardVersionIds: [],
    });
  });

  it("tracks the last (standard, version) chosen at upload in memory", () => {
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

  it("removes active versions that are absent from the current database", () => {
    useFiltersStore.setState({ activeStandardVersionIds: ["current", "stale", "current-2"] });

    useFiltersStore.getState().reconcileActiveStandardVersions(["current", "current-2"]);

    expect(useFiltersStore.getState().activeStandardVersionIds).toEqual([
      "current",
      "current-2",
    ]);
  });

  it("does not persist analysis targets or filters in browser storage", () => {
    useFiltersStore.getState().setChecklistActive(true);
    useFiltersStore.getState().toggleTargetUnit("metric");

    expect(localStorage.getItem("doc-reviewer-filters")).toBeNull();
  });
});
