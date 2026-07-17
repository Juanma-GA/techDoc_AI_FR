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
  // Normes cibles actives (multi-select Parametres, parite preview) : liste de
  // version IDs fusionnees a chaque analyse et appliquees a chaque upload.
  activeStandardVersionIds: string[];
  toggleSeverity: (s: Severity) => void;
  toggleKind: (k: RuleKind) => void;
  setHideAccepted: (v: boolean) => void;
  setShowUnitConversions: (v: boolean) => void;
  setTargetUnit: (v: "metric" | "imperial" | "auto") => void;
  setLastStandard: (standardId: string | null, versionId: string | null) => void;
  toggleActiveStandardVersion: (versionId: string) => void;
  clearActiveStandards: () => void;
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
      activeStandardVersionIds: [],
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
      toggleActiveStandardVersion: (versionId) =>
        set({
          activeStandardVersionIds: get().activeStandardVersionIds.includes(versionId)
            ? get().activeStandardVersionIds.filter((x) => x !== versionId)
            : [...get().activeStandardVersionIds, versionId],
        }),
      clearActiveStandards: () => set({ activeStandardVersionIds: [] }),
    }),
    { name: "pdf-reviewer-filters" },
  ),
);
