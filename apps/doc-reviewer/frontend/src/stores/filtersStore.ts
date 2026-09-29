import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { RuleKind, Severity, SourceKind } from "../types/domain";

type FiltersState = {
  severities: Severity[];
  kinds: RuleKind[];
  hideAccepted: boolean;
  showUnitConversions: boolean;
  // Systemes d'unites cibles : selection MULTIPLE (metric et/ou imperial).
  // Vide OU les deux => comportement "auto" (conversion bidirectionnelle).
  targetUnits: ("metric" | "imperial")[];
  // Cible « checklist » (toggle runtime) : quand false, l'analyse exclut les
  // regles importees de checklist (llm_nl / manual). Independant des normes.
  checklistActive: boolean;
  lastStandardId: string | null;
  lastStandardVersionId: string | null;
  // Normes cibles actives (multi-select Parametres, parite preview) : liste de
  // version IDs fusionnees a chaque analyse et appliquees a chaque upload.
  activeStandardVersionIds: string[];
  // Filtre de la liste des anomalies (panneau reviewer) : source (checklist /
  // norme / regle / transverse) et regle precise. `null` = pas de filtre.
  sourceKindFilter: SourceKind | null;
  ruleCodeFilter: string | null;
  toggleSeverity: (s: Severity) => void;
  toggleKind: (k: RuleKind) => void;
  setHideAccepted: (v: boolean) => void;
  setShowUnitConversions: (v: boolean) => void;
  toggleTargetUnit: (u: "metric" | "imperial") => void;
  setChecklistActive: (v: boolean) => void;
  setLastStandard: (standardId: string | null, versionId: string | null) => void;
  toggleActiveStandardVersion: (versionId: string) => void;
  reconcileActiveStandardVersions: (validVersionIds: string[]) => void;
  clearActiveStandards: () => void;
  setSourceKindFilter: (v: SourceKind | null) => void;
  setRuleCodeFilter: (v: string | null) => void;
};

export const useFiltersStore = create<FiltersState>()(
  persist(
    (set, get) => ({
      severities: ["info", "warning", "error"],
      kinds: ["standard", "custom", "units", "layout"],
      hideAccepted: false,
      showUnitConversions: true,
      targetUnits: [],
      // Opt-in strict : rien d'actif par defaut (aucune norme, checklist OFF,
      // aucune unite) => aucune regle appliquee tant que l'utilisateur ne
      // selectionne pas explicitement une cible.
      checklistActive: false,
      lastStandardId: null,
      lastStandardVersionId: null,
      activeStandardVersionIds: [],
      sourceKindFilter: null,
      ruleCodeFilter: null,
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
      toggleTargetUnit: (u) =>
        set({
          targetUnits: get().targetUnits.includes(u)
            ? get().targetUnits.filter((x) => x !== u)
            : [...get().targetUnits, u],
        }),
      setChecklistActive: (v) => set({ checklistActive: v }),
      setLastStandard: (standardId, versionId) =>
        set({ lastStandardId: standardId, lastStandardVersionId: versionId }),
      toggleActiveStandardVersion: (versionId) =>
        set({
          activeStandardVersionIds: get().activeStandardVersionIds.includes(versionId)
            ? get().activeStandardVersionIds.filter((x) => x !== versionId)
            : [...get().activeStandardVersionIds, versionId],
        }),
      reconcileActiveStandardVersions: (validVersionIds) =>
        set((state) => {
          const validIds = new Set(validVersionIds);
          const activeIds = state.activeStandardVersionIds.filter((id) => validIds.has(id));
          const unchanged =
            activeIds.length === state.activeStandardVersionIds.length &&
            activeIds.every((id, index) => id === state.activeStandardVersionIds[index]);
          return unchanged ? {} : { activeStandardVersionIds: activeIds };
        }),
      clearActiveStandards: () => set({ activeStandardVersionIds: [] }),
      setSourceKindFilter: (v) => set({ sourceKindFilter: v }),
      setRuleCodeFilter: (v) => set({ ruleCodeFilter: v }),
    }),
    { name: "doc-reviewer-filters" },
  ),
);

/** Cible d'unite envoyee au backend a partir de la selection multiple :
 *  aucune cochee => "none" (aucune verif d'unite) ; une seule => cette unite ;
 *  les deux => "auto" (bidirectionnel). Modele opt-in : rien coche => rien. */
export function effectiveTarget(
  units: ("metric" | "imperial")[],
): "metric" | "imperial" | "auto" | "none" {
  if (units.length === 0) return "none";
  const selectedUnit = units[0];
  return units.length === 1 && selectedUnit ? selectedUnit : "auto";
}
