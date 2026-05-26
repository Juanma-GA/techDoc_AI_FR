import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { RuleKind, Severity } from "../types/domain";

type FiltersState = {
  severities: Severity[];
  kinds: RuleKind[];
  hideAccepted: boolean;
  showUnitConversions: boolean;
  targetUnit: "metric" | "imperial" | "auto";
  lastStandardId: string | null;
  lastStandardVersionId: string | null;
  toggleSeverity: (s: Severity) => void;
  toggleKind: (k: RuleKind) => void;
  setHideAccepted: (v: boolean) => void;
  setShowUnitConversions: (v: boolean) => void;
  setTargetUnit: (v: "metric" | "imperial" | "auto") => void;
  setLastStandard: (standardId: string | null, versionId: string | null) => void;
};

export const useFiltersStore = create<FiltersState>()(
  persist(
    (set, get) => ({
      severities: ["info", "warning", "error"],
      kinds: ["s1000d", "standard", "custom", "units"],
      hideAccepted: false,
      showUnitConversions: true,
      targetUnit: "auto",
      lastStandardId: null,
      lastStandardVersionId: null,
      toggleSeverity: (s) =>
        set({
          severities: get().severities.includes(s)
            ? get().severities.filter((x) => x !== s)
            : [...get().severities, s],
        }),
      toggleKind: (k) =>
        set({
          kinds: get().kinds.includes(k)
            ? get().kinds.filter((x) => x !== k)
            : [...get().kinds, k],
        }),
      setHideAccepted: (v) => set({ hideAccepted: v }),
      setShowUnitConversions: (v) => set({ showUnitConversions: v }),
      setTargetUnit: (v) => set({ targetUnit: v }),
      setLastStandard: (standardId, versionId) =>
        set({ lastStandardId: standardId, lastStandardVersionId: versionId }),
    }),
    { name: "pdf-reviewer-filters" },
  ),
);
